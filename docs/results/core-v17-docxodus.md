# Docxodus on core-v17: rendering-fidelity fixes, October 2026

This records the measurement of Docxodus issues #1115, #1116 and #1119–#1126 against the LibreOffice reference track. Word references are still pending, so these numbers say nothing about Word fidelity.

## Contract

| Item | Value |
|---|---|
| Suite | `core-v17`: 92 cases, the 85 original inputs byte-identical, plus 7 authored controls and regression inventories (#23, #25, #36) |
| Reference | LibreOffice 25.8.7.3, `libreoffice-equivalent-controls` track. Proven controls: #17 boundary merge, #16 unit-valued minimum heights, #18 logical indentation, plus the earlier legacy page-number and exact-height controls |
| Metric | v2: bidi formatting controls excluded from visible text (#19), one-pixel union canvas (#22) |
| Reference bundle | Registered in [run 38517776349](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38517776349). Reference-provider calibration **100**, every reference passes its own declared checks |
| Candidates | Measured against that same bundle via `reference_run` (#37), so the results are comparable with `bench compare` |

## Headline

| | Baseline: Docxodus main `a56b4484384770a1b30a8680179667afec4523d5` | All fixes integrated: `ff403b1dc7f5dccdda46a61db14e313773a403f6` |
|---|---|---|
| Run | [38517776349](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38517776349) | [38520853246](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38520853246) |
| **Suite score** | **70.377** | **97.774** |
| Columns | 99.45 | 99.45 |
| Images | 99.16 | 99.16 |
| Notes | 32.42 | 92.75 |
| Paragraphs | 83.51 | 98.44 |
| Tables | 37.35 | 99.07 |
| Mandatory pass rate | 75.0% (23 cases fail) | **100%** |
| Close-match rate | 35.9% | 85.9% |

The integrated commit merges these Docxodus PRs:

| PR | Fixes | Bench issue |
|---|---|---|
| #1131 | #1115 | #26 |
| #1132 | #1121 | #30 |
| #1133 | #1122 | #31 |
| #1134 | #1126 | #35 |
| #1135 | #1116 | #27 |
| #1137 | #1120 | #29 |
| #1136 | #1119 | #28 |
| #1138 | #1125 | #34 |
| #1139 | #1123 | #32 |

#1124 has no renderer change; see below.

## Regressions and differences `bench compare --tolerance 0` reports

- **`paragraphs-zero-width` 100.00 → 99.98 and `paragraphs-overindented-word` 99.98 → 99.96.** These are SSIM changes on a single inline glyph. With #1123, such single-spaced documents use the fractional text painter. Their previous exact score came from a coincidental whole-pixel match. Every mandatory check, including the glyph regions, still passes.
- **The four `notes-explicit-breaks-*` cases now have 3 pages instead of 5 or 6.** This is the intended fix. The reference has 3 pages, and every ledger line is on the reference page.

No other case score decreased.

## Remaining differences (not mandatory failures)

- **`paragraph-contract` 92.07, unchanged (#1124).** Docxodus's justified lines end at 539.99pt. The LibreOffice reference's lines end 0.64–1.29pt short of the 540pt margin. Glyph advances agree closely. No LibreOffice-specific change was made. The later [Word capture and Times New Roman variant](paragraph-contract-word.md) retain this original baseline; Word's capture of the Liberation Serif input is ineligible because it substitutes the font.
- **Long notes about 90.5.** The note lines match the reference positions within 0.5pt. What remains is the continuation separator's style: a full-width light rule versus LibreOffice's 2-inch black rule.
- **Dashed border cards about 95.3–95.6.** LibreOffice paints a fixed 8pt dash with a 2.5pt gap. Docxodus keeps its CSS dash rhythm. Word's pattern is not captured.

## Desired and measured evidence

All crops are 144 DPI with identical physical regions. "Desired" is the reference capture; "baseline" and "final" are the Docxodus PDFs before and after.

| Feature | Desired (reference) | Baseline `a56b448` | Final `ff403b1` |
|---|---|---|---|
| #1115 simple PAGE field, page 2 header | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1115-simple-page-field-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1115-simple-page-field-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1115-simple-page-field-measured.png) |
| #1116 explicit 0.25pt border card | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1116-thin-border-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1116-thin-border-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1116-thin-border-measured.png) |
| #1126 border spacing on indented, grouped and hanging cards | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1126-border-spacing-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1126-border-spacing-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1126-border-spacing-measured.png) |
| #1119/#1120 long note, page 2 | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1119-1120-long-note-p2-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1119-1120-long-note-p2-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1119-1120-long-note-p2-measured.png) |
| #1121 55pt ledger rows 15–20 | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1121-row-precision-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1121-row-precision-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1121-row-precision-measured.png) |
| #1122 36pt minimum-height rows | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1122-minimum-rows-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1122-minimum-rows-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1122-minimum-rows-measured.png) |
| #1122 exact 18pt row with overflowing content | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1122-exact-overflow-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1122-exact-overflow-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1122-exact-overflow-measured.png) |
| #1123 single-spaced running stories, page 2 top | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1123-single-spacing-p2-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1123-single-spacing-p2-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1123-single-spacing-p2-measured.png) |
| #1125 606.5 × 878.5pt page, bottom edge | ![desired](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1125-fractional-edge-ink-desired.png) | ![baseline](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/baseline/1125-fractional-edge-ink-measured.png) | ![final](https://raw.githubusercontent.com/JSv4/Docxodus/6ad98edd6ff83a5b90d35e43c8e177213ea41b28/docs/architecture/fidelity-gap-evidence/core-v17/final/1125-fractional-edge-ink-measured.png) |
## Per-PR measurements

| PR | Run | Suite | Main effect |
|---|---|---|---|
| #1131 (#1115) | [38513473245](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38513473245) | 71.429 | three simple-field cases 0 → 99.96–99.99 |
| #1132 (#1121) | [38513478570](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38513478570) | 71.382 | vertical-merge ledgers 76–78 → 98.0–98.3 |
| #1134 (#1126) | [38513489059](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38513489059) | 70.566 | border cards 86–91 → 95.3–99.8 |
| #1135 (#1116, on #1126) | [38514813800](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38514813800) | 70.881 | `paragraphs-border-spacing-indented` 0 → 88.9; thin card 99.82 |
| #1138 (#1125) | [38513499777](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38513499777) | 71.400 | fractional pages 0 → 99.89; edge ink 0 → 91.80 |
| #1139 (#1123) | [38515173482](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38515173482) | 70.755 | page margins 91.56 → 99.60; multipage 80.55 → 99.06 |
| #1133 (#1122, on #1121), final bundle | [38520856292](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38520856292) | 82.721 | tables 37.35 → 99.07; every row-height inventory 0 → 97.96–99.84 |
| #1137 + #1136 (#1120, #1119) | [38513445329](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38513445329) | 82.443 | long notes 0 → 90.2–90.8 |

These runs used the first `core-v17` bundle ([38505393578](https://github.com/JSv4/docx-fidelity-bench/actions/runs/38505393578), main also 70.377). The suite changed afterwards only in `tables-row-height-exact-overflow`, which #36 revised so it no longer depends on clipped-text extraction (Docxodus #1140). None of these PRs touch that case except #1133, whose re-run against the final bundle is listed below.

Intermediate runs, kept as visible history:
- #1126's first version regressed the border cards to 0. Its text sat at x=71.75, because CSS lays a 1pt border out at 0.75pt.
- #1123's second version dropped the 12pt indentation cases to 0, because of SVG origin snapping. Its third version dropped `paragraph-contract` to 86.93 through 1/64-pixel layout drift.
- #1122's first version rendered exact rows in a fallback font, because cloned XML nodes lost their style annotations.

Each was fixed at its cause and re-measured. The full ledger is in the linked runs.

## Per-case results

✗ marks a mandatory-check failure (case scored 0).

| Case | Category | Baseline main a56b448 | Integrated ff403b1 | Change |
|---|---|---|---|---|
| `columns-continuous` | columns | 99.46 | 99.46 | +0.00 |
| `columns-balanced` | columns | 99.43 | 99.43 | +0.00 |
| `columns-break` | columns | 99.46 | 99.46 | +0.00 |
| `paragraph-contract` | paragraphs | 92.07 | 92.07 | +0.00 |
| `paragraph-heading` | paragraphs | 99.20 | 99.95 | +0.75 |
| `paragraph-keep` | paragraphs | 99.19 | 99.50 | +0.30 |
| `notes-footnote` | notes | 95.66 | 95.66 | +0.00 |
| `notes-endnote` | notes | 98.88 | 98.88 | +0.00 |
| `tables-nested` | tables | 99.77 | 99.77 | +0.00 |
| `tables-margins` | tables | 99.74 | 99.74 | +0.00 |
| `images-square` | images | 99.44 | 99.44 | +0.00 |
| `images-tight` | images | 99.46 | 99.46 | +0.00 |
| `drawings-textbox-absolute` | images | 98.96 | 98.96 | +0.00 |
| `drawings-textbox-empty-host` | images | 98.97 | 98.97 | +0.00 |
| `drawings-textbox-zero-relative` | images | 98.96 | 98.96 | +0.00 |
| `paragraphs-header-empty` | paragraphs | 99.96 | 99.96 | +0.00 |
| `paragraphs-header-hidden` | paragraphs | 99.96 | 99.96 | +0.00 |
| `paragraphs-inline-control` | paragraphs | 100.00 | 100.00 | +0.00 |
| `paragraphs-zero-width` | paragraphs | 100.00 | 99.98 | -0.02 |
| `paragraphs-overindented-word` | paragraphs | 99.98 | 99.96 | -0.02 |
| `tables-vmerge-early-control` | tables | 76.42 | 98.13 | +21.70 |
| `tables-vmerge-early-merged` | tables | 76.42 | 98.13 | +21.70 |
| `tables-vmerge-boundary-control` | tables | 77.38 | 97.99 | +20.61 |
| `tables-vmerge-boundary-merged` | tables | 77.53 | 98.30 | +20.76 |
| `paragraphs-line-breaks-plain-control` | paragraphs | 96.56 | 96.56 | +0.00 |
| `paragraphs-line-breaks-plain-breaks` | paragraphs | 96.56 | 96.56 | +0.00 |
| `paragraphs-line-breaks-blanks-control` | paragraphs | 96.56 | 96.56 | +0.00 |
| `paragraphs-line-breaks-blanks-breaks` | paragraphs | 96.56 | 96.56 | +0.00 |
| `paragraphs-page-size-height-control` | paragraphs | 99.89 | 99.99 | +0.10 |
| `paragraphs-page-size-height-fractional` | paragraphs | 0.00 ✗ | 99.99 | +99.99 |
| `paragraphs-page-size-width-control` | paragraphs | 99.89 | 99.99 | +0.10 |
| `paragraphs-page-size-width-fractional` | paragraphs | 0.00 ✗ | 99.99 | +99.99 |
| `paragraphs-page-number-ordinary-field` | paragraphs | 99.99 | 99.99 | +0.00 |
| `paragraphs-page-number-ordinary-simple-field` | paragraphs | 0.00 ✗ | 99.99 | +99.99 |
| `paragraphs-page-number-ordinary-legacy` | paragraphs | 99.98 | 99.98 | +0.00 |
| `paragraphs-page-number-restarted-field` | paragraphs | 99.98 | 99.98 | +0.00 |
| `paragraphs-page-number-restarted-simple-field` | paragraphs | 0.00 ✗ | 99.98 | +99.98 |
| `paragraphs-page-number-restarted-legacy` | paragraphs | 99.76 | 99.76 | +0.00 |
| `notes-explicit-breaks-paragraph-control` | notes | 0.00 ✗ | 90.22 | +90.22 |
| `notes-explicit-breaks-breaks` | notes | 0.00 ✗ | 90.22 | +90.22 |
| `notes-explicit-breaks-blanks-paragraph-control` | notes | 0.00 ✗ | 90.77 | +90.77 |
| `notes-explicit-breaks-blanks-breaks` | notes | 0.00 ✗ | 90.77 | +90.77 |
| `paragraphs-border-size-single-omitted` | paragraphs | 90.71 | 99.99 | +9.28 |
| `paragraphs-border-size-single-zero` | paragraphs | 90.71 | 99.99 | +9.28 |
| `paragraphs-border-size-single-thin` | paragraphs | 90.85 | 99.99 | +9.14 |
| `paragraphs-border-size-dashed-omitted` | paragraphs | 86.13 | 95.33 | +9.20 |
| `paragraphs-border-size-dashed-zero` | paragraphs | 86.13 | 95.33 | +9.20 |
| `paragraphs-border-size-dashed-thin` | paragraphs | 88.83 | 95.55 | +6.71 |
| `paragraphs-indentation-pt` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-in` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-cm` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-mm` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-pc` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-pi` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-twips` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-small-pt` | paragraphs | 96.79 | 98.11 | +1.31 |
| `paragraphs-indentation-small-twips` | paragraphs | 96.79 | 98.11 | +1.31 |
| `paragraphs-indentation-twips-logical-only` | paragraphs | 96.92 | 98.34 | +1.42 |
| `paragraphs-indentation-small-twips-logical-only` | paragraphs | 96.79 | 98.11 | +1.31 |
| `paragraphs-page-margins-pt` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-in` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-cm` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-mm` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-pc` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-pi` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-twips` | paragraphs | 91.56 | 99.60 | +8.04 |
| `paragraphs-page-margins-multipage-pt` | paragraphs | 80.55 | 99.06 | +18.51 |
| `paragraphs-page-margins-multipage-twips` | paragraphs | 80.55 | 99.06 | +18.51 |
| `paragraphs-page-margins-small-mm` | paragraphs | 99.87 | 99.99 | +0.13 |
| `paragraphs-page-margins-small-twips` | paragraphs | 99.81 | 99.98 | +0.17 |
| `tables-row-height-pt` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-in` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-cm` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-mm` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-pc` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-pi` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-twips` | tables | 0.00 ✗ | 99.72 | +99.72 |
| `tables-row-height-fractional-pt` | tables | 0.00 ✗ | 97.96 | +97.96 |
| `tables-row-height-fractional-twips` | tables | 0.00 ✗ | 97.96 | +97.96 |
| `tables-row-height-multipage-pt` | tables | 0.00 ✗ | 98.37 | +98.37 |
| `tables-row-height-multipage-twips` | tables | 0.00 ✗ | 98.37 | +98.37 |
| `tables-row-height-exact-pt` | tables | 99.74 | 99.74 | +0.00 |
| `tables-row-height-exact-twips` | tables | 99.74 | 99.74 | +0.00 |
| `paragraphs-standard-trash-control` | paragraphs | 95.77 | 95.77 | +0.00 |
| `paragraphs-standard-trash-zero` | paragraphs | 95.77 | 95.77 | +0.00 |
| `paragraphs-standard-trash-upper` | paragraphs | 95.77 | 95.77 | +0.00 |
| `paragraphs-standard-trash-lower` | paragraphs | 95.77 | 95.77 | +0.00 |
| `tables-vmerge-boundary-merged-kept` | tables | 77.53 | 98.30 | +20.76 |
| `tables-row-height-exact-overflow` | tables | 0.00 ✗ | 99.84 | +99.84 |
| `paragraphs-page-number-numpages-simple-field` | paragraphs | 0.00 ✗ | 99.96 | +99.96 |
| `paragraphs-border-spacing-indented` | paragraphs | 0.00 ✗ | 89.07 | +89.07 |
| `paragraphs-page-size-edge-ink` | paragraphs | 0.00 ✗ | 99.48 | +99.48 |
