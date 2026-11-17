# pdf.js (vendored)

Prebuilt files from `pdfjs-dist@4.10.38` (Apache-2.0, see `LICENSE`), used by
`frontend/src/components/PdfViewer.vue` to render PDFs in-page on every device.

| File here | Source in the npm package |
|---|---|
| `pdf.min.js` | `legacy/build/pdf.min.mjs` |
| `pdf.worker.min.js` | `legacy/build/pdf.worker.min.mjs` |
| `standard_fonts/` | `standard_fonts/` |

The files are ES modules renamed from `.mjs` to `.js` so nginx serves them with
a JavaScript MIME type. They are vendored (not a package.json dependency)
because `pdfjs-dist` pulls native `canvas` optional dependencies into the
lockfile that the frontend never needs.

To upgrade: `npm pack pdfjs-dist@<version>`, copy the three sources above, and
bump `PDFJS_VERSION` in `PdfViewer.vue` (it is the cache-busting query string).
