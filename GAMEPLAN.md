# Gameplan

Working doc for queued PRs. Pick one up by spinning a fresh terminal/branch
and using the writeup below as the briefing.

---

## Parked — Certificate render redesign (Chromium + vector frame)

**Status:** designed, awaiting go-ahead from user. Not started.

**Why parked:** dev will briefly go down for the Docker image rebuild, so we
launch this when the user explicitly says go.

**Full plan:** `.claude/docs/plans/2026-05-19-certificate-render-redesign.md`

**One-line summary:** switch the Certificate print format off wkhtmltopdf
(third attempt at a layout fix still spilled onto page 2 — see
`~/Downloads/26i261rhbl.pdf`) to Frappe's `pdf_generator: "chromium"`,
self-host the three fonts, replace `cert-frame.png` with inline SVG, add an
admin preview page, gate CI with a Playwright e2e that asserts
`pageCount === 1` across 3 worst-case variants.

**Open decisions:** all 5 sign-off questions in the plan doc are answered.
Only remaining gate is "user says go."

**Effort:** ~3 days work + ~30min image rebuild per environment.

**Entry sequence when picking this up:**
1. Branch `feat/certificate-chromium-render` from `develop`.
2. Open a doc-only commit/PR with the plan first so the design is
   reviewable + linked from implementation commits.
3. Walk Tasks 1–7 from the plan doc.

---

## Shipped (kept for reference, remove when stale)

- **PR #142** (2026-05-19) — Survey UX: Next/Submit + required questions. Merged + deployed.
- **PR #143** (2026-05-19) — Certificate one-page (wkhtmltopdf flex rewrite). Merged + deployed, but didn't fully solve the problem — superseded by the Chromium redesign above.

---

## Original briefings (kept for diff reference until next deploy)

## PR #3 — Course survey UX: Next/Submit + required questions

**Branch suggestion:** `fix/survey-next-submit-required`

### Symptom (client report, 2026-05-19)

> "The pagination of the course survey is very confusing. 'Submit' should
> not be showing from the beginning, because no one would think to click
> the numbers on the pagination. Each question should be required and the
> 'Submit' should say 'Next' until they fill in each one."

### Root cause

The course completion survey is rendered by `frontend/src/components/Quiz.vue`
when the underlying `LMS Quiz` has `is_survey=true`. Survey quizzes are stored
with `show_answers=false` (no right/wrong feedback). Two bugs interact:

1. **Template gate too narrow** — `Quiz.vue:322-336`:
   ```vue
   <Button v-else-if="activeQuestion != questions.length && quiz.data.show_answers"
       @click="nextQuestion()">Next</Button>
   <Button variant="solid" v-else @click="handleSubmitClick()">Submit</Button>
   ```
   When `show_answers=false`, the Next branch is unreachable and *every*
   question shows "Submit" as its primary CTA. Users either:
   - Click Submit on question 1 and dismiss (losing the rest of the survey), or
   - Stare at the pagination dots wondering whether they're supposed to click them.

2. **Handler short-circuits surveys** — `Quiz.vue:881-886`:
   ```js
   const nextQuestion = () => {
       if (!quiz.data.show_answers) return   // <-- early-out
       if (questionDetails.data?.type == 'Open Ended') addToLocalStorage()
       markCurrentAttempted()
       resetQuestion()
   }
   ```
   So even if we expose the Next button on surveys, today it does nothing.

### Fix

1. **Template** — drop `&& quiz.data.show_answers` from the Next-button
   `v-else-if`. Show Next whenever `activeQuestion != questions.length`,
   regardless of survey/graded.
2. **Handler** — remove the `if (!quiz.data.show_answers) return` line in
   `nextQuestion`. The remaining logic (`addToLocalStorage` for Open Ended,
   `markCurrentAttempted`, `resetQuestion`) is already survey-safe.
3. **Required** — disable Next/Submit when the current question is
   unanswered. The component already has `selectedOptions` for choice
   questions and `possibleAnswer` for typed answers; gate the buttons'
   `:disabled` on those. Use a `currentQuestionAnswered` computed:
   - For `Choices` (single/multi): at least one `selectedOptions[i] !== 0`
   - For `Open Ended` / `Short Text`: `possibleAnswer.value` non-empty
4. **Side benefit** — this also fixes silent-graded quizzes (`show_answers=false`,
   `is_survey=false`), which today have the same Submit-on-every-question bug.

### Test plan

- e2e (`e2e/survey-required-flow.spec.ts` — new):
  - Open a course completion survey, confirm question 1 shows "Next" (not
    "Submit"), confirm Next is disabled until an answer is entered, click
    through all questions confirming the button stays "Next" until the last
    one, where it becomes "Submit".
- Manual: smoke an existing graded quiz to confirm we didn't regress the
  Check → Next flow when `show_answers=true`.

### Files

- `frontend/src/components/Quiz.vue` — template (lines 322-336) and
  `nextQuestion` handler (~line 881).
- `e2e/survey-required-flow.spec.ts` — new.

### Risk

Low. The change widens the "Next" branch and removes a short-circuit; the
"required" gating only blocks the button (no silent data changes). Worst
realistic regression is a quiz that genuinely allows skipping questions
losing that ability — but our current behavior (Submit-on-every-question)
means no one is currently using that affordance intentionally.

---

## PR #4 — Certificate PDF fits on one page

**Branch suggestion:** `fix/certificate-one-page`

### Symptom (client report, 2026-05-19)

Certificate spills onto two pages. Page 1 has the logo / title / recipient /
course title; page 2 has only the signatures + date orphaned at the top.
Example: `~/Downloads/PPT4ed course certification - no good.pdf`.

> "We already tried to fix this" — previous attempts patched pixel offsets
> but didn't hold.

### Root cause

The Frappe Print Format `Certificate`
(`lms/lms/print_format/certificate/certificate.json`) uses an 11in × 8.5in
landscape page rendered by **wkhtmltopdf**, with every section
absolutely positioned:

```css
.cert-title       { position: absolute; top: 2in;    ... }
.cert-recipient-name { position: absolute; top: 3.85in; ... }
.cert-course-title   { position: absolute; top: 5.15in; ... }
.cert-signatures     { position: absolute; top: 6.3in;  ... }
.cert-footer         { position: absolute; bottom: 0.75in; ... }
```

Why this breaks despite math that should fit:

- wkhtmltopdf does not consistently honor `overflow: hidden` on the
  containing `.cert-page` when computing page breaks. Even when content
  visually clips, wkhtmltopdf may still generate a second page based on
  total document height.
- Frappe wraps print-format output in its own container. Any padding the
  wrapper adds shifts every absolute `top:` calculation against the actual
  page edge.
- Pixel-tweaks (the previous fixes) drift back to broken every time the
  Frappe print wrapper or wkhtmltopdf version changes.

### Approach: rebuild layout in flow (chosen 2026-05-19)

Stop fighting absolute positioning. Replace with a single flex column inside
a fixed-size inner frame, with `page-break-inside: avoid` on the container.

Outline:

```html
<div class="cert-page">
    <img class="cert-frame" ...>
    <div class="cert-content">
        <!-- flex column, vertically distributed -->
        <div class="cert-logos">...</div>
        <h1 class="cert-title">Certificate of Completion</h1>
        <p class="cert-subtitle">PPT4ed in collaboration with...</p>
        <p class="cert-recipient-name">{{ name }}</p>
        <p class="cert-license">{{ license_info }}</p>
        <p class="cert-preamble">for successful completion...</p>
        <h2 class="cert-course-title">{{ course_title }}</h2>
        <div class="cert-signatures">...</div>
        <div class="cert-footer">...</div>
    </div>
</div>
```

```css
@page { size: 11in 8.5in landscape; margin: 0; }
html, body { margin: 0; padding: 0; }

.cert-page {
    width: 11in;
    height: 8.5in;
    position: relative;
    overflow: hidden;
    page-break-inside: avoid;
    break-inside: avoid;
}
.cert-frame {
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    z-index: 0;
}
.cert-content {
    position: relative; z-index: 1;
    width: 10in; height: 7.5in;        /* 0.5in safety margin all sides */
    margin: 0.5in;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    text-align: center;
}
```

Why this is more robust:

- No element depends on a pixel `top:` value. The flex column distributes
  whatever content is there across the available height. If Frappe's
  wrapper adds 8px of padding, the content shrinks by 8px instead of
  pushing the footer off the page.
- 0.5in safety margin on all sides gives wkhtmltopdf breathing room even
  when fonts load slightly larger than expected.
- `page-break-inside: avoid` is a hint to keep the whole certificate on one
  page even if computed height drifts slightly.

### Variations on content height

The cert has variable content depending on the doc:

- License line (`doc.license_info`) is conditional — present for some users.
- Approvals list (`CEU Discipline Link`) is N items — usually 1-3 lines.
- Instructors signature blocks — usually 2, sometimes 1.
- `is_event` swaps logo block and adds a venue line.

The flex layout handles all of these because nothing is hard-positioned.
Manually verify the tallest case (license + 3 approval disciplines +
2 instructors) still fits.

### Test plan

- Render the certificate for a known failing case (Power of Play
  certificate for a user with a license) on dev. Confirm 1 page.
- Render for the tallest variant (event certificate with venue + 3
  disciplines + 2 instructors). Confirm 1 page.
- Render minimal variant (no license, no approvals, 1 instructor). Confirm
  it still looks balanced (flex `space-between` spreads short content out
  unflatteringly — may need `justify-content: flex-start` with controlled
  margins instead. Decide at implementation time.)
- Eyeball alignment: title centered, recipient name centered, signatures
  centered as a group.

### Files

- `lms/lms/print_format/certificate/certificate.json` — `html` and `css`
  fields. This is the only file to change. No code changes.

### Risk

Medium. The print format is a delivery artifact; misformatting is visible
to every cert recipient. Mitigations:
- Test against a small set of known cert variants on dev before prod.
- Keep a copy of the current JSON in the PR description so rollback is
  one commit revert.
- Don't change instructor signature rendering (cursive font block) — that
  part of the layout is fine.

### Why we didn't pick the alternatives

- **Tighten existing absolute layout** — same brittle approach previous
  attempts used; will drift back to broken.
- **Switch to chromium PDF generator** — Frappe supports it but requires
  server-side chromium install and verifying every other print format
  (badges, payment receipts) still renders correctly. Out of scope for
  fixing one cert.

---

## Conventions for both

- Branch from `develop`, squash-merge, deploy via `/deploy-dev` skill.
- Both are frontend/print-format only — no Python, no schema, no deps.
  Standard `git pull` + `bench build --app lms` + asset sync (PR #3) or
  just `git pull` + `bench migrate` (PR #4 — print format JSON is loaded
  via fixtures-style import on migrate).
- Add Playwright tests where the surface is web (PR #3). For PR #4, manual
  PDF inspection is sufficient — no automation for wkhtmltopdf output.
