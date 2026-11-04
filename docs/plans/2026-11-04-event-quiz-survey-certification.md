# Gameplan: Event quiz + survey certification, signer credentials, certificate preview

**Source:** Garrett / Teresa Hans meeting, 2026-11-04 (Loom recap) + Teresa's 2026-10-30 email.
**Branch:** `feat/event-quiz-survey-certification` from `develop`. PR targets `develop`. Stop before prod.
**Immediate use case:** the Turtlebrace event + its online quiz (80% pass), in-person and remote attendees.

---

## 0. Audit: what already exists on `develop` (do not rebuild)

Verified against `develop` at `f6bbf507` (PR #238 merged). No open PRs.

| Brief item | Status | Where |
|---|---|---|
| Event has a graded credit quiz AND a separate ungraded survey | **Built** (PRs #230-#233) | `LMS Event.credit_verification` (Manual / Survey Only / Online Quiz / In-Person Quiz), `credit_quiz`, `survey_quiz`, `credit_passing_percentage` |
| Certificate only mints when survey submitted AND quiz passed, either order | **Built** | `lms_event.py: maybe_auto_mint_event_certificate` (gates: certification, no existing cert, `has_submitted_event_survey`, `has_passed_credit_quiz`) |
| Idempotent issuance, no duplicate certs | **Built** | mint helper `exists` check + `LMSCertificate.validate_duplicate_certificate`; `test_mint_helper_is_idempotent` |
| Server-side enforcement on both submit paths | **Built** | `api.submit_event_survey`, `api.submit_event_quiz`, `ceu_event_admin.record_event_quiz_results` all call the same mint helper |
| Learner next-step cues (survey open / quiz open / cert badge) | **Built** | `EventDashboard.vue` (banners + `credit-progress` block), tabs in `EventDetail.vue` |
| Admin per-attendee survey / quiz / certificate status + Issue certificate | **Built** (#235) | `AdminEventDashboard.vue`, `ceu_event_admin.get_event_credit_status`, `issue_event_certificates` |
| Signer selection, 2-signer max, no auto-add of presenters | **Built** (#215 courses, #238 events) | `LMS Event.certificate_signers` (Certificate Signer child), `validate_certificate_signers` |
| Reusable signer credentials field | **Built** | `User.credentials` (custom field, fixture), self-edit in `EditProfile.vue` |
| Credentials printed after signer name, toggle per event | **Built** | `LMS Event.show_signer_credentials`; template `sig_name = full_name ~ ", " ~ credentials` |
| Certificate shows title, CEU hours, date, venue, signatures | **Built** | `lms/lms/print_format/certificate/certificate.json` (Jinja, `pdf_generator: chrome`) |
| Certificate preview page | **Partial** | `AdminCertificatePreview.vue` at `/admin/certificate-preview/:certName` only loads an **existing** `LMS Certificate` via `/printview`. No sample mode, no event entry point, no explicit role gate |
| Explicit "Require survey for course credit" setting | **Missing** | Today an attached `survey_quiz` is *always* required. There is no way to attach an optional survey |
| Admin surface to edit another user's credentials | **Missing** | Only self-edit via profile. PPT admins have no Desk (hard rule), so Global Admin cannot set a presenter's credentials today |
| "Live" format label on event certificates | **Missing** | Template prints `On-Demand Course` for on-demand courses only; events print no format line |
| Event date on event certificates | **Gap / decision** | Template prints `Date: doc.issue_date` (mint date), not the event date |
| Turtlebrace event on dev | **Not present** | Dev has no event with a credit quiz. Prod is the authoring source (hard rule), so the real record lives on `app.ppt4ed.org` |

Takeaway: workstream 1 is mostly a settings + validation + UI-copy change, not a new gating engine. The genuinely new code is the sample preview endpoint, the credentials admin edit, the format/date rendering, and tests.

---

## 1. Facts that need confirmation (not code)

Record these in the PR under "Setup dependencies". None block the code work.

1. **Event date conflict.** Teresa's 2026-10-30 email says November 6; the Loom recap says Saturday (November 7). Do not change `start_date`, `event_days`, title, or cert date. Report the configured value from prod and ask Teresa.
2. **Answer key.** Teresa flagged possible wrong markings. Her email may carry correct answers as HTML highlighting that vanishes in plain text. Pull the **original HTML** of the 2026-10-30 email (Gmail connector: search `from:Teresa` around 2026-10-30, read the thread's raw HTML, look for `background-color` / `<mark>` / bold on option text). Diff against the quiz's `is_correct_*` flags and **report**; do not edit the key without her confirmation.
3. **Final survey content.** If the real evaluation questions are not available, build with a dev-only fixture survey (prefix `Garrett Test`) and list the content dependency.
4. **Teresa's editing access.** `LMSEvent.validate` calls `ensure_instructors_have_moderator_role(...)`: adding her to `instructors` silently grants **Moderator**. Decide with Garrett whether that is acceptable before touching her roles. Not automatic.
5. **Modules / PowerPoint / supplemental resources.** Content delivery from Teresa. Existing chapter/lesson + Resource-type course flow handles it; nothing to build.
6. **Prod read of the Turtlebrace event** was blocked by the session's prod-read guard. Garrett runs the read-only command in §7 and pastes the output, or grants the read.

---

## 2. Design decisions (recommendation first)

### D1. `require_survey_for_credit` semantics
- Add `LMS Event.require_survey_for_credit` (Check, label **"Require survey for course credit"**, `insert_after: survey_quiz`, `depends_on: certification`). Mirror the field on `LMS Course` only if the course cert path needs it (it does not for this brief; skip).
- `has_submitted_event_survey` returns True unless `require_survey_for_credit` is on. `Survey Only` mode implies the flag (the survey *is* the gate): treat as on regardless of the checkbox.
- **Backward compatibility patch** `lms.patches.v2_0.backfill_require_survey_for_credit`: set `=1` where `certification=1 AND survey_quiz IS NOT NULL AND credit_verification != 'Manual'`. This reproduces today's behavior exactly for every existing event, so "requirement off" only exists for events edited after the deploy. Idempotent (`UPDATE ... WHERE require_survey_for_credit = 0`), no ALTER.
- Validation in `LMSEvent.validate_credit_settings` (new): flag on + no `survey_quiz` → throw "Require survey for course credit needs a survey attached"; `survey_quiz` must have `is_survey=1`; `Online Quiz` mode needs `credit_quiz` with `is_survey=0`. Note `get_credit_passing_percentage` uses the **quiz's** `passing_percentage` when `credit_quiz` is set, so the 80% lives on the `LMS Quiz`, not the event field.
- `get_event_details` exposes `survey_required`; `submit_event_survey` still accepts optional surveys (no gating change there).

### D2. Sample certificate preview
- Backend `lms.lms.ceu_event_admin.preview_event_certificate(event, as_pdf=0)`, gated by `_require_event_admin()` (uses `LMS_MODERATOR_ROLES`). Builds an **unsaved** `LMS Certificate` (`member` = session user, `member_name` = "Sample Participant", `issue_date` = today, `ceu_hours` copied from `event.credit_hours`, `ceu_disciplines` from the event's CEU Discipline Links) and renders with `frappe.get_print("LMS Certificate", None, "Certificate", doc=doc, no_letterhead=1)`. Never `insert()`. PDF via the same chrome generator (`pdf_generator=chrome`).
- Mark the doc `doc.is_sample_preview = 1`; template adds a diagonal **SAMPLE – not a valid certificate** watermark + "Sample Participant" when set. The earned path never sets it.
- Frontend: "Preview certificate" button on `AdminEventDashboard.vue` (admin only) opening the existing `AdminCertificatePreview.vue` in a new **sample mode** (route `/admin/certificate-preview/event/:eventName`), reusing its iframe + Download PDF. Keep the existing by-name mode.
- Tests assert: no new `LMS Certificate`, no `Email Queue`, no `LMS Quiz Submission` / registration change; Guest + LMS Student get `PermissionError`.

### D3. Certificate content for events
- **Format line:** print `Live Course` under the title for events (both `event_type` values are live); keep `On-Demand Course` for on-demand courses. Wording to confirm with Garrett; cheap to change.
- **Date line:** recommend `Date:` = event `start_date` for events (range if `event_days` spans multiple days), issue date for courses. Today the cert prints mint date, which drifts from the event date whenever a learner finishes the survey later. This is a visible behavior change; confirm before merge, implement behind the same template branch so it is a one-line revert.
- Long names: add `cert-sig-name--long` class when `sig_name` > ~28 chars; cover in `certificate-render.spec.ts` (one-page assertion already exists).
- Missing credentials: already safe (no dangling comma; test exists).

### D4. Credentials admin editing surface
- In `EventForm.vue`, next to each selected Certificate Signer show their current `credentials` with an inline edit (and same in `CourseForm.vue` if trivial). Saves through new `lms.lms.ceu_event_admin.set_signer_credentials(user, credentials)` gated by moderator roles. Shows existing value, never pre-fills a guess, overwrites only on explicit save.
- Do not bulk-set anyone's credentials. The PR seeds nothing.

### D5. Concurrency hardening (small, optional but recommended)
- Two simultaneous submit calls can both pass the `exists` check in `maybe_auto_mint_event_certificate`. Wrap the check + insert in a row lock on the `LMS Event Registration` row (`frappe.db.get_value(..., for_update=True)`) so the second caller sees the first cert. `validate_duplicate_certificate` is the last line of defense; a test with two sequential calls already exists, add one that mocks the race.

---

## 3. Work breakdown (in order)

### WS0. Setup
- [ ] `git checkout develop && git pull`, branch `feat/event-quiz-survey-certification`.
- [ ] Back up dev before any migration: `bench --site devlms.ppt4ed.org backup --with-files` (see §6).

### WS1. Require-survey setting (D1)
- [ ] `lms/lms/doctype/lms_event/lms_event.json`: add `require_survey_for_credit`; bump `modified`.
- [ ] `lms_event.py`: `CREDIT_EVENT_FIELDS` += field; `has_submitted_event_survey` honours flag / Survey Only; new `validate_credit_settings` wired in `validate()`.
- [ ] `lms/patches/v2_0/backfill_require_survey_for_credit.py` + `patches.txt` entry (`#04-11-2026`).
- [ ] `utils.get_event_details`: expose `survey_required`.
- [ ] `EventForm.vue`: checkbox under Survey Quiz with help text; `AdminEventDashboard.vue` survey column shows "(optional)" when not required; `EventDashboard.vue` copy: "Submit your feedback to receive your certificate" only when required, else "Optional".
- [ ] `ceu_event_admin.get_event_credit_status`: `survey_required` in payload; `survey_submitted` stays as-is.

### WS2. Certificate rendering (D3)
- [ ] `certificate.json` html: fetch `event_type`, `start_date`, `end_date` for events; `Live Course` line; event date line; long-name class; SAMPLE watermark hook (`doc.get("is_sample_preview")`). Bump print format `modified` (migrate only reloads when newer; else `import_file_by_path(force=True)`).

### WS3. Sample preview (D2)
- [ ] `ceu_event_admin.preview_event_certificate` + `_build_preview_certificate(event)`.
- [ ] `router.js` route + `AdminCertificatePreview.vue` sample mode (`eventName` prop → iframe `src` from endpoint, `Download PDF` → `as_pdf=1`).
- [ ] `AdminEventDashboard.vue`: "Preview certificate" button (icon Buttons need `:label`, frappe-ui drops `data-testid`; use `aria-label`-safe label text for e2e).

### WS4. Credentials editing (D4)
- [ ] `ceu_event_admin.set_signer_credentials` (+ `get_signer_profiles(users)` returning `full_name`, `credentials`, `signature_text`).
- [ ] `EventForm.vue` signer rows: show credentials, inline edit, save.

### WS5. Hardening (D5)
- [ ] Row lock in `maybe_auto_mint_event_certificate`.

### WS6. Tests (see §4)

### WS7. Deploy to dev + verification (see §6), then PR (see §8).

---

## 4. Test matrix

Backend: `lms/lms/test_event_credit_verification.py` (reuse `_make_event`, `_make_quiz`, `_make_user`, email/webhook patches already in `setUp`) and `lms/lms/doctype/lms_certificate/test_lms_certificate.py` (`TestCertificatePrintFormat._render`, `_signature_names`). All data prefixed `Garrett Test`.

| Requirement | Existing | Add |
|---|---|---|
| Failed quiz + submitted survey → nothing | `test_online_quiz_fail_then_pass` (partial) | `test_failed_quiz_with_survey_does_not_mint` |
| Passed quiz + missing required survey → nothing | `test_online_quiz_pass_then_survey_mints_on_survey` | assert explicitly with flag on |
| Passed quiz + required survey → exactly one cert | same | count `LMS Certificate` == 1, CEU ledger == 1 |
| Survey before quiz → mint only on pass | `test_in_person_score_before_survey_mints_on_survey` | online variant |
| Requirement off → quiz pass alone mints; attached survey optional | none | `test_optional_survey_does_not_gate` |
| Flag on, no survey attached → config error | none | `test_require_survey_without_survey_rejected` |
| Survey Only mode ignores checkbox | none | `test_survey_only_mode_always_requires_survey` |
| Backfill patch idempotent, preserves behavior | none | `test_backfill_require_survey_patch` |
| Repeated submissions / issuance → no duplicates | `test_mint_helper_is_idempotent`, `test_admin_issues_certificates_to_selected_attendees` | race test with `for_update` |
| Unauthorized preview / edit of another learner | `test_record_validation_and_permissions`, `test_manual_issue_validation_and_permissions` | `test_preview_requires_moderator`, `test_set_credentials_requires_moderator` |
| Preview has zero side effects | none | `test_preview_creates_nothing` (certs, Email Queue, submissions, ledger) |
| Credentials on/off, 2 signers | `test_event_credentials_print_only_when_toggle_is_on`, `test_event_signers_override_instructor_order` | preview renders credentials identically |
| Long names, Live / On-Demand labels | `test_long_title_gets_long_class` family | `test_event_prints_live_format`, `test_long_signer_name_class` |
| Event date on cert (if D3 approved) | none | `test_event_certificate_prints_event_date` |

E2E (Playwright, dev, headed where Stripe is not involved):
- `e2e/event-credit-verification.spec.ts`: extend the "online" test with the require-survey toggle: pass quiz → badge "Submitted/Pending", no cert; submit survey → cert link. Second run: flag off → cert after quiz alone.
- `e2e/certificate-render.spec.ts`: add preview variant + long signer names, assert `pageCount === 1`.
- New `e2e/event-certificate-preview.spec.ts`: moderator opens preview (watermark text visible, Download PDF works); student hits 403; DB unchanged (count via `page.request` with CSRF token, per the Playwright CSRF rule).
- Mobile pass: 390px viewport on `EventDashboard` banners + Survey/Quiz tabs, screenshots into `screenshots-walkthrough/`.

Run: `bench --site devlms.ppt4ed.org set-config allow_tests true` → `bench run-tests --app lms --module lms.lms.test_event_credit_verification` and `--module lms.lms.doctype.lms_certificate.test_lms_certificate` → set `allow_tests` back to false. Frontend: `yarn --cwd frontend lint` / type check only; no local `vite build` (hangs on Windows; the dev build is the gate).

---

## 5. Turtlebrace verification checklist (read-only, prod)

Run from the host as read-only, then record in the PR:

```
ssh -i ~/.ssh/id_ed25519 root@45.55.89.232 'docker exec lms-backend-1 bench --site app.ppt4ed.org execute frappe.client.get_list --kwargs "{\"doctype\":\"LMS Event\",\"filters\":[[\"title\",\"like\",\"%urtle%\"]],\"fields\":[\"name\",\"title\",\"start_date\",\"end_date\",\"start_time\",\"end_time\",\"event_type\",\"credit_hours\",\"certification\",\"credit_verification\",\"credit_quiz\",\"credit_passing_percentage\",\"survey_quiz\",\"show_signer_credentials\",\"published\",\"venue\"]}"'
```
Then for the returned `credit_quiz` / `survey_quiz` names:
```
... execute frappe.client.get_value --kwargs "{\"doctype\":\"LMS Quiz\",\"filters\":{\"name\":\"<credit_quiz>\"},\"fieldname\":[\"title\",\"passing_percentage\",\"max_attempts\",\"is_survey\",\"show_answers\"]}"
... execute frappe.client.get_list --kwargs "{\"doctype\":\"Certificate Signer\",\"filters\":{\"parent\":\"<event>\"},\"fields\":[\"signer\",\"idx\"]}"
... execute frappe.client.get_list --kwargs "{\"doctype\":\"LMS Event Day\",\"filters\":{\"parent\":\"<event>\"},\"fields\":[\"date\",\"start_time\",\"end_time\"]}"
```
Confirm:
- [ ] `certification = 1`, `credit_verification = Online Quiz`, `credit_quiz` set, `survey_quiz` set and `is_survey = 1`.
- [ ] **Quiz** `passing_percentage = 80` (the event-level `credit_passing_percentage` is ignored when a quiz is linked).
- [ ] `max_attempts` is what Teresa wants (0 = unlimited).
- [ ] Event date / `event_days` vs Nov 6 (email) / Nov 7 (recap): report only.
- [ ] `credit_hours`, `event_type`, `venue`, ≤2 signers, `show_signer_credentials`, each signer's `User.credentials` populated.
- [ ] Early-cert check: with Online Quiz mode and a survey attached, `maybe_auto_mint_event_certificate` cannot mint on quiz pass alone (code path verified on develop; after this PR the backfill patch sets `require_survey_for_credit = 1` for this event; re-verify post-migrate on prod when that deploy happens).
- [ ] Answer key: diff quiz `is_correct_*` against the HTML-highlighted email; report, do not change.

---

## 6. Dev deploy + verification procedure

Follow `/deploy-dev` exactly; summary of the gates it enforces:
1. PR merged to `develop` first (or, for pre-merge dev testing, check out the branch on the host bind mount `/opt/ppt4ed-lms` and restore `develop` afterwards; note it in the PR).
2. **Backup:** `docker exec lms-backend-1 bench --site devlms.ppt4ed.org backup --with-files`.
3. `git pull` on the **host**, then `chown -R 1000 /opt/ppt4ed-lms` (root-owned files break bench build).
4. `bench --site devlms.ppt4ed.org migrate` (schema + patch + print format reload; if the print format does not pick up, `import_file_by_path(..., force=True)`).
5. `bench build --app lms` **only after saving the Frappe entries of `assets.json`; restore them after**; then `docker cp` built assets into the frontend container. Never bare `bench build`.
6. `bench clear-cache`; restart `lms-backend-1` (hooks untouched by this plan, but clear-cache anyway after the print-format reload).
7. Smoke **both** `/login` and `/lms/login`.
8. Verify in browser: event Settings shows the new checkbox; Admin Dashboard shows Preview certificate; open the preview PDF and inspect it (watermark, signers, credentials, hours, Live line, date); run the learner flow as a `Garrett Test` student on desktop + 390px mobile.

No real emails: dev Email Account stays as configured; test runs patch `send_certification_email` / `send_confirmation_email`; manual browser runs use `garrett.test.*@example.com` accounts only.

---

## 7. Rollback

- Code: revert the merge commit on `develop`, `git pull` on host, `bench build --app lms` with the same Frappe-hash guard, clear-cache, restart.
- Schema: the new Check column is harmless if left; the patch only writes `1` into it. No data to unwind.
- Print format: restore the previous `certificate.json` via `import_file_by_path(force=True)`.
- Backup from step 6.2 covers everything else.

---

## 8. PR contents

- Change summary per workstream, with the audit table from §0 so reviewers see what was reused.
- Migration steps (patch name, print-format reload note).
- Test results (backend module output, Playwright summary, anything not run and why).
- Before/after screenshots: Event Settings, Admin Dashboard, learner banners (desktop + mobile), preview PDF page.
- Rollback (§7).
- **Setup dependencies (not code):** final survey content, Teresa's answer-key confirmation, module list + PowerPoint + resources delivery, editing-access decision (Moderator grant implication), event-date confirmation.
- Dev walkthrough for Garrett + Teresa: log in as moderator → Events → Turtlebrace clone on dev (`Garrett Test Turtlebrace`) → Settings (quiz, survey, checkbox, signers, credentials) → Dashboard → Preview certificate → then as a test student: take quiz (fail, then pass) → submit survey → certificate link.

---

## 9. Out of scope (explicitly)

- Course-level `require_survey_for_credit`, Razorpay/`paid_certificate` cleanup, Batch→Event rename debt, new content/resource system, granting Teresa roles, any prod deploy or prod data change.
