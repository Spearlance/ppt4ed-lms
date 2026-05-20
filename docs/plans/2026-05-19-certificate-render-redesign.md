# Certificate Render Redesign — Switch to Chromium + Vector Frame

**Date:** 2026-05-19
**Branch (proposed):** `feat/certificate-chromium-render`
**Status:** Design doc — awaiting approval before implementation
**Supersedes:** `GAMEPLAN.md` § "PR #4 — Certificate PDF fits on one page" (PR #143, deployed but still spills onto page 2)

## Why this PR exists

Certificates are the highest-stakes artifact on the platform: therapists submit them to state licensing boards as proof of CEU completion, and frame them as professional credentials. They must look polished, be reliably one page, and never glitch.

Two attempts to fix the layout under wkhtmltopdf have failed:
1. **Previous attempts (before this work):** pixel-tweaked the absolute layout. Regressed each time the Frappe wrapper or wkhtmltopdf version changed.
2. **PR #143 (deployed 2026-05-19):** rebuilt the layout as a flex column with `page-break-inside: avoid` and `overflow: hidden`. Almost works — the visible page-1 content renders cleanly — but a sliver of the `cert-frame.png` decorative border bleeds onto a second page (`~/Downloads/26i261rhbl.pdf` from QA download).

The root cause is not the layout. It is **wkhtmltopdf's page-height computation**: even when content visually fits in 8.5in and `overflow: hidden` is set, wkhtmltopdf can still emit a second page if any rendered element's box extends past the page boundary by a sub-pixel amount. We have hit this three times now. It is not fixable from within the print format.

This PR replaces wkhtmltopdf with **headless Chromium** for the certificate print format only, and redesigns the decorative frame as **inline SVG** so it never bleeds past the page edge.

## Requirements

**Reliability — non-negotiable:**

- Always exactly one PDF page, across every content variant:
  - Long course title (3 lines at 24pt — currently caps at ~95 characters before wrapping past safe height)
  - Long recipient names (multi-part hyphenated names)
  - `license_info` present vs. absent
  - 1, 2, or 3 `CEU Discipline Link` rows
  - 1 or 2 instructors
  - Event variant (PPT + PPT4ed dual logo + venue line) vs. course variant
- Deterministic across Docker image rebuilds — no font fetch from `fonts.googleapis.com` at render time.
- Vector graphics for all decorative elements — borders, dividers, signature lines. PNG raster art at 72dpi looks pixelated when zoomed in PDF viewers (people screenshot and zoom).
- Embedded fonts in the PDF stream — no "missing font, substituting Helvetica" surprises on other people's Adobe Reader.

**Aesthetic:**

- Faithful to the current Playfair Display / Inter / Great Vibes typography (current design is good; redesign is out of scope for this PR).
- Replace the raster `cert-frame.png` with a vector SVG frame that scales perfectly and never crops past the page edge.
- Subtle refinements where vector-precision allows: cleaner corner ornaments, hairline rule under the recipient name, signature lines that align exactly with the cursive glyphs above them.

**Operational:**

- A "Preview Certificate" admin URL that renders the cert as HTML in a browser (no PDF round-trip) for design iteration.
- Playwright e2e test that mints a cert PDF for each worst-case variant and asserts `pageCount === 1`. CI catches regressions before they ship.

## Architecture decision: Chromium in the backend image (Option A)

Two architectures were considered:

| | A. Chromium in backend container | B. Dedicated Playwright sidecar |
|---|---|---|
| Cert renders by | Frappe's `pdf_generator: "chromium"` → Playwright → headless Chromium, in-process | Backend POSTs cert HTML to sidecar, sidecar returns PDF bytes |
| Image bloat | ~250MB added to backend image | Sidecar is ~500MB on its own, backend unchanged |
| Inter-service coupling | None — same container | New HTTP boundary, secret sharing, healthcheck |
| Future PDF features | Reuses the in-container Chromium | Sidecar is a reusable rendering service |
| Operational complexity | One image to manage | Two services, deploy ordering, network isolation |
| Frappe-native | Yes — `pdf_generator: "chromium"` is built in | No — custom integration code |

**Choosing A.** The only argument for B is "we'll need this for other PDFs later," but we have no other PDFs on the near-term roadmap (badges and receipts work fine under wkhtmltopdf for now). YAGNI says we don't build a sidecar today for hypothetical tomorrow. If we ever do need transcripts / resume exports / etc., we can extract the rendering path into a sidecar then.

## Implementation scope

### Task 1 — Add Playwright + Chromium to the backend Docker image

**Files:** `pyproject.toml`, the deploy server's `frappe_docker/images/custom/Containerfile`

- Add `playwright` to `pyproject.toml` dependencies.
- Update `Containerfile` to install Playwright system deps and the Chromium browser binary at image build time:
  ```dockerfile
  RUN pip install playwright \
      && playwright install --with-deps chromium \
      && chown -R frappe:frappe /home/frappe/.cache/ms-playwright
  ```
- Set `PLAYWRIGHT_BROWSERS_PATH=/home/frappe/.cache/ms-playwright` env in the container so the `frappe` user can find the binary.
- Bake in (do not download at runtime — that would mean every cold-start re-downloads chromium).

**Verification command (post-build):**
```bash
docker exec lms-backend-1 python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK', b.version); b.close(); p.stop()"
```

### Task 2 — Self-host the cert fonts

**Files:** `lms/public/fonts/` (new), `lms/public/css/cert-fonts.css` (new)

Currently the print format loads fonts from `fonts.googleapis.com`. Chromium will honor this — but it means every PDF render is a network call to Google. For a regulated artifact on the user's license, we cannot tolerate "the cert is wrong because Google was slow."

Self-host the three font families under `/assets/lms/fonts/`:

- `PlayfairDisplay-Regular.woff2` (used for "Certificate of Completion")
- `Inter-Regular.woff2` + `Inter-Medium.woff2` + `Inter-Bold.woff2` (body)
- `GreatVibes-Regular.woff2` (signatures)

Inline `@font-face` declarations in the cert CSS pointing at `{{ base_url }}/assets/lms/fonts/...`. Drop the `<link href="fonts.googleapis.com">` line entirely.

License check: all three fonts are SIL Open Font License or similar — bundling-and-redistributing is permitted. **Action: confirm this at implementation time** by reading each font's LICENSE.txt from Google Fonts.

### Task 3 — Redesign the decorative frame as inline SVG

**Files:** `lms/lms/print_format/certificate/certificate.json` (html field)

Remove `cert-frame.png` entirely. Replace with an inline `<svg>` at the same z-index, sized exactly `11in × 8.5in`, with:

- Outer rounded rectangle, 2pt stroke, 0.25in inset from page edge
- Inner thin rectangle, 0.5pt stroke, 0.05in inside the outer
- Subtle ornamental corners (small flourishes — keep them tasteful, not Victorian)
- Solid white fill so it doesn't show through any background

The SVG is part of the HTML stream, not an external asset — no risk of asset URL failures, no DPI mismatch with the page.

I will design the SVG borders in the implementation PR. They should be vector-clean and approximately match the current PNG's aesthetic (printed-frame look), not radically different.

### Task 4 — Switch the print format generator + clean up wkhtmltopdf-specific code

**Files:** `lms/lms/print_format/certificate/certificate.json`

- `"pdf_generator": "wkhtmltopdf"` → `"pdf_generator": "chromium"`
- Remove the `<meta name="pdfkit-*">` tags from the HTML — Chromium ignores them, they're dead code under the new renderer
- Verify `@page { size: 11in 8.5in landscape; margin: 0; }` is respected (it is, per Frappe-expert research)
- Keep `page-break-inside: avoid` as belt-and-suspenders, even though Chromium handles single-page output correctly via fixed dimensions alone

The flex-column layout from PR #143 stays — it's correct CSS. Only the renderer changes.

### Task 5 — Admin Preview Certificate page

**Files:** `frontend/src/pages/admin/CertificatePreview.vue` (new), `frontend/src/router.js`

A dev-only route at `/lms/admin/certificate-preview/<cert-name>` that:

- Loads the same Jinja template, but renders it in the browser as HTML (calls a backend endpoint that returns the rendered HTML string)
- Shows the certificate at exact print dimensions (11in × 8.5in scaled to fit viewport)
- Has a "Download PDF" button that hits the existing print URL — for spot-checking that HTML preview matches PDF output
- Restricted to roles with `LMS Admin` (existing role)

This is the single highest-leverage thing for design iteration. Right now every design tweak requires: edit JSON → migrate → force-import → restart backend → download PDF. With the preview, it's: edit JSON → reload page.

### Task 6 — Playwright e2e for cert page count

**Files:** `e2e/certificate-render.spec.ts` (new)

Login as admin → POST `frappe.client.insert` to create a fixture LMS Certificate for each of these variants:

1. **Tallest variant:** long course title (`The Power of Play: Linking Play to Language, Cognitive, Social-Emotional & Literacy Development` — currently in seed data) + `license_info` set + 3 CEU disciplines + 2 instructors
2. **Event variant:** event-type cert with venue + 2 instructors
3. **Minimal variant:** no license, no approvals, 1 instructor, short course title

For each, hit `/api/method/frappe.utils.print_format.download_pdf?...&format=Certificate` and assert the response is a PDF with exactly one page. Use `pdf-parse` or `pdfjs-dist` for page-count assertion.

Test gates CI on `develop` — never merge a cert layout change that produces two pages.

### Task 7 — Documentation + memory updates

- Update `.claude/rules/deployment-safety.md` to note that backend image rebuilds are now required when cert layout changes touch Playwright/Chromium versions.
- Save a memory entry: "Chromium PDF generator path" — covers the env var, the verification command, and how to add new chromium-rendered print formats.
- Remove the now-stale memory `feedback_print_format_reload.md`? No — keep it; it still applies to any non-chromium print format change.

## Rollout

This PR requires a **full Docker image rebuild**, which is rarer for us than bind-mount deploys. Sequence:

1. **Branch + design review** — this doc lands first as a doc-only commit so we have alignment on scope. Then implementation work proceeds.
2. **Build image locally on the deploy server** — `cd /opt/frappe_docker && docker build ... -t ppt4ed/lms:dev-chromium .` (~10min build).
3. **Verify image** — `docker run --rm ppt4ed/lms:dev-chromium python3 -c "from playwright.sync_api import sync_playwright; ..."` before swapping containers.
4. **Swap containers on dev** — `docker compose -f lms.yaml down && docker compose -f lms.yaml up -d` after pushing the image. Bind-mounted `/opt/ppt4ed-lms` carries the JSON + frontend changes.
5. **Migrate** for the print format JSON change, then force-import per `feedback_print_format_reload.md`.
6. **Smoke test** on dev with the 3 variants in Task 6. **If any variant renders 2 pages, do not proceed to prod.**
7. **Prod rollout:** same sequence on prod. Tag image as `ppt4ed/lms:prod-2026-MM-DD-chromium`. Keep the previous prod tag (`prod-2026-05-13`) ready for one-command rollback.

**Rollback path:** revert the JSON `pdf_generator` field to `wkhtmltopdf` (bind-mount edit, ~30s deploy). The image keeps Playwright installed but unused. No data is lost — certs are rendered on demand, not stored.

## Out of scope (explicitly)

- **Other print formats.** Badges, payment receipts, and any other Frappe print formats stay on wkhtmltopdf. Migrating them is a separate effort and not justified by current issues.
- **Cert redesign.** Typography choices, brand colors, layout proportions all stay. This PR is "render the same design reliably," not "make the design better." (A redesign PR can follow; happy to scope that separately if you want.)
- **Migrating existing certs.** Certs aren't stored as files — they're regenerated on each download. Users who re-download an old cert will get the new render automatically. No backfill needed.
- **Sidecar / microservice architecture.** Punted to whenever a second high-stakes PDF use case shows up.
- **Print-on-paper testing.** I will eyeball PDFs in a viewer. Verifying ink-on-paper output requires the user to actually print one and is a manual QA item, not engineering scope.

## Decisions (signed off 2026-05-19)

1. **SVG frame:** faithful reproduction of the current PNG aesthetic in vector form. Professional and symbolic of a real certificate — not over the top, no Victorian flourishes. Keep the current "two-rectangle frame with subtle corner ornaments" silhouette.

2. **Fonts:** keep Playfair Display + Inter + Great Vibes. Self-host all three under `/assets/lms/fonts/`.

3. **Image rebuild timing:** dev going down briefly during the rebuild + container swap is acceptable. **Start when user gives go-ahead** — not before. Prod cutover is a later, separate ask.

4. **Cert preview admin page:** admin-only. Live at `/lms/admin/certificate-preview/<name>`. Not exposed to instructors.

5. **Playwright in backend image:** approved. (Side note: Playwright is also our e2e test runner — that lives on the CI/dev machine, not inside the backend container. This PR adds it to a new place: the backend image itself, so Chromium is available to Frappe at PDF-render time.)

## Estimated effort

| Task | Effort |
|---|---|
| 1. Playwright in image | 0.5 day (mostly waiting for Docker build cycles) |
| 2. Self-host fonts | 0.5 day |
| 3. SVG frame design | 0.5 day |
| 4. JSON switch + cleanup | 0.25 day |
| 5. Admin preview page | 0.5 day |
| 6. e2e test | 0.5 day |
| 7. Docs + memory | 0.25 day |
| **Total** | **~3 days work** |

Plus ~30min on each environment for the image rebuild + rollout sequence.
