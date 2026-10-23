# Default tab interval against Word

This records the Word evidence behind the `core-v51` default tab interval cases for [Docxodus #1269](https://github.com/JSv4/Docxodus/issues/1269). It adjudicates the zero-interval case only. It is not a registered reference: the captured inputs are the issue's own reproducers, not this repository's fixtures, and Word substituted the requested font.

## Capture

The three inputs are the issue's reproducers, `repros/2026-10-20/inputs/tabs-{0,12,720}.docx` at Docxodus commit `f0081a653dc9a2b56c3461ae579aef7f376fcf5c`. Each holds one Liberation Serif paragraph: `Observatory inventory`, then a tab and `North`, a tab and `East`, a tab and `South`, then `Copper lens`. The paragraph has no custom tab stops and no indent. The three files differ only in `w:defaultTabStop`, which is 0, 12 or 720 twips.

Each file was opened in Word for the web and exported through **File > Export > Download as PDF**. No repair prompt appeared and Word reported no build number. Every PDF is one Letter page (612 by 792pt), created by Microsoft Word, and embeds only `TimesNewRomanPSMT`. Word substituted Times New Roman for Liberation Serif. The two fonts are metric-compatible, so horizontal positions remain comparable, but the substitution makes the captures ineligible as references under [Word reference registration](../WORD_CAPTURE.md). `bench reference import` cannot register them in any case, because their input digests are not this repository's fixtures.

| Input | Input SHA-256 | Word PDF SHA-256 |
| --- | --- | --- |
| `tabs-0.docx` | `209a286c9ed65f31aaf0c39a67eb631b66fb7fa3ce90ebf438c61beab16e425e` | `ee898ef96129e2f73e999e02284265c052b169cb2bf015fa59d1b113f6691ad9` |
| `tabs-12.docx` | `56a1f16d75eeccc9d95a02e116dd8d0ea8c670bfba41f3eb1dd6c9f43dfef60e` | `44b2e2c2b9814ede904f52bad829a078a7552263448f386edff38ba10ea0a4bf` |
| `tabs-720.docx` | `4f11cd379a35dcb655c7c8f7b9828de888db99a5b99f1a70974fc388f98db874` | `ef4fb690029464838cd3e7b37bd958a8bbdb5632974b669908ef8a6da4a15ad7` |

## What the coordinates establish

The table gives each word's glyph left edge in points (left margin 72pt). `inventory` ends at 179.989pt in all three Word PDFs.

| `w:defaultTabStop` | Word `North` | Word `East` | Word `South` | LibreOffice 25.8.7.3 `North` / `East` / `South` |
| ---: | ---: | ---: | ---: | --- |
| 720 | 216.10 | 252.10 | 288.13 | 216.1 / 252.1 / 288.1 |
| 12 | 180.58 | 208.85 | 229.85 | each word within 0.6pt of the one before |
| 0 | 180.33 | 208.33 | 229.10 | 213.9 / 249.4 / 284.8 |

- At 720 twips Word and LibreOffice agree on the half-inch grid.
- At 12 twips Word advances each tab to the next 12-twip (0.6pt) multiple from the margin. There is no minimum interval and no fallback.
- At 0 Word gives each tab no width. The residues after the preceding words, 0.34, 0.02 and 0.20pt, are within Word's positioning grid. Word neither falls back to the half-inch default that applies when the element is omitted, nor uses any visible interval.
- LibreOffice treats 0 as unset and uses its own 1.25cm default.

## How the cases use it

`tabs-default-interval-0` declares Word-adjudicated regions. Each of `TabNorth`, `TabEast` and `TabSouth` must start no more than 3pt left of where a zero-width tab puts it (after the preceding word and its space), and at least 4pt before LibreOffice's 1.25cm stop. A half-inch fallback lies further right still. As the [scoring contract](../SCORING.md) describes, these assertions bind candidates and Word references but not LibreOffice captures, so the LibreOffice reference stays eligible. A candidate that follows Word on this case is compared with LibreOffice pages whose words sit on a 1.25cm grid, which caps its raster score there.

`tabs-default-interval-12` is not adjudicated: Word and LibreOffice agree there, and its regions bind every capture. The control, `tabs-default-interval-720-control`, follows the reference.
