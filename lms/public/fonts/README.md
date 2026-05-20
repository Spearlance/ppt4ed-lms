Self-hosted fonts for the Certificate print format.

Each font is the latin-subset woff2 from Google Fonts, served at
`/assets/lms/fonts/` and referenced via `@font-face` in
`lms/lms/print_format/certificate/certificate.json`. Files are committed
so the cert renders identically regardless of whether the deploy server
can reach `fonts.gstatic.com` at render time.

| File | Family | Source | License |
|---|---|---|---|
| `inter-latin.woff2` | Inter (variable, weights 100-900) | https://fonts.google.com/specimen/Inter | SIL OFL 1.1 — © 2016 The Inter Project Authors (https://github.com/rsms/inter) |
| `playfair-display-latin.woff2` | Playfair Display (variable) | https://fonts.google.com/specimen/Playfair+Display | SIL OFL 1.1 — © 2017 The Playfair Project Authors (https://github.com/clauseggers/Playfair) |
| `great-vibes-latin.woff2` | Great Vibes 400 | https://fonts.google.com/specimen/Great+Vibes | SIL OFL 1.1 — Copyright (c) 2011 by TypeSETit, LLC |

The SIL Open Font License 1.1 is the same text for all three families and
permits bundling and redistribution. Full license text:
https://openfontlicense.org/open-font-license-official-text/

If you upgrade a font, refresh from
https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Playfair+Display:wght@400&family=Great+Vibes&display=swap
(modern UA) and replace the corresponding file. Subsetting beyond latin
is not currently needed — all cert content is English.
