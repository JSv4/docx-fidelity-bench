# Inline paragraph frames

These 28 original cases cover [Docxodus #1487](https://github.com/JSv4/Docxodus/issues/1487): grouped inline frames in the body, header, footer and table cells; separate frames with intervening text; page-end admission; and a header frame that reaches into body text or a full-width table. Each reproduction has an ordinary-flow or floating-frame control. The suite is `core-v93` (673 cases); the preceding 645 input bytes and declarations are unchanged apart from the shared generator hash.

All 28 packages have zero Open XML SDK 3.5.1 Microsoft365 findings. Inputs use original Aster labels and separately provisioned Liberation Serif. No product test helper or document was imported. [Source validation](source-validation.json) binds these results to the registered inputs.

## Local comparison

| Renderer | Mandatory checks | Controls |
|---|---:|---|
| LibreOffice 25.8.7.3 | 28 / 28 | Native reference |
| Main `97c304f7` | 14 / 28 | 14 pass |
| Uncommitted candidate on `97c304f7` | 28 / 28 | All 14 complete page-image sets byte-identical to main |

These are local public-export diagnostics, not production CI scores. Main used the tree-identical `8ba4e112` runtime; the candidate uses the ten-file source snapshot and runtime asset hashes recorded in [local-evidence.json](local-evidence.json). Both invoke the public standalone HTML/PDF exporter with strict fonts, final review view, hidden comments and sandboxed Chromium. Exact inputs, PDFs, render reports, physical page geometry, extracted text and screenshot panels are hash-bound in that report.

LibreOffice lays these inline frame paragraphs out as ordinary text. Native Word probes elsewhere in the product investigation show wrapping beside `around` frames and following text below `notBeside` frames. The benchmark therefore checks both valid arrangements without claiming identical pixels or a font-matched Word reference. These exact Aster inputs have no registered Word capture. Isolated native spacing verification, final source review and production CI remain pending; this evidence does not complete the product issue.

## What the checks prove

Complete token inventories, declared fonts, page count and physical page geometry remain mandatory. The new versioned `non-overlapping-markers` assertion rejects overlapping word boxes for each frame line and the following label. A tolerance of at most 0.5 pt accommodates adjacent-line font metrics. Independent regions pin the labels to their pages and source-derived layout bands. Separate frames must retain their authored horizontal band; following text may remain in ordinary flow or beside the 180 pt frame. The table rows must clear the six-line header and keep the native two-page distribution. Floating `wrap=none` controls intentionally permit overlap and do not declare separation assertions.

The assertions check selected word boxes rather than every glyph, full frame paint or exact wrapping. Raster comparison remains part of the production harness; no score formula, font check or existing mandatory contract is relaxed.

[Actual PDF mutation checks](assertion-mutants.json) move the first or last frame label onto the following label while preserving every other mandatory check; only the separation assertion fails. Moving the following label sideways, off paper or onto another page also fails. [Independent review mutations](review-mutants.json) additionally reproduced false passes for a packed following label, a displaced second frame and a table row without clearance. Tighter position bands and the second-frame/intervening-label pair close those gaps.

## Every case

Each linked sheet includes every physical page at 96 DPI and 100% scale. Panels are neither cropped nor resampled; absent pages are labeled explicitly. The columns are LibreOffice, main and candidate.

| Case / complete screenshot | Main | Candidate |
|---|---|---|
| [frames-inline-body-around](frames-inline-body-around.png) | Fail | Pass |
| [frames-inline-body-below](frames-inline-body-below.png) | Fail | Pass |
| [frames-inline-body-floating-control](frames-inline-body-floating-control.png) | Pass | Pass |
| [frames-inline-body-normal-control](frames-inline-body-normal-control.png) | Pass | Pass |
| [frames-inline-body-separated](frames-inline-body-separated.png) | Fail | Pass |
| [frames-inline-body-separated-normal-control](frames-inline-body-separated-normal-control.png) | Pass | Pass |
| [frames-inline-cell-around](frames-inline-cell-around.png) | Fail | Pass |
| [frames-inline-cell-below](frames-inline-cell-below.png) | Fail | Pass |
| [frames-inline-cell-floating-control](frames-inline-cell-floating-control.png) | Pass | Pass |
| [frames-inline-cell-normal-control](frames-inline-cell-normal-control.png) | Pass | Pass |
| [frames-inline-footer-around](frames-inline-footer-around.png) | Fail | Pass |
| [frames-inline-footer-below](frames-inline-footer-below.png) | Fail | Pass |
| [frames-inline-footer-floating-control](frames-inline-footer-floating-control.png) | Pass | Pass |
| [frames-inline-footer-normal-control](frames-inline-footer-normal-control.png) | Pass | Pass |
| [frames-inline-footer-separated](frames-inline-footer-separated.png) | Fail | Pass |
| [frames-inline-footer-separated-normal-control](frames-inline-footer-separated-normal-control.png) | Pass | Pass |
| [frames-inline-header-around](frames-inline-header-around.png) | Fail | Pass |
| [frames-inline-header-below](frames-inline-header-below.png) | Fail | Pass |
| [frames-inline-header-floating-control](frames-inline-header-floating-control.png) | Pass | Pass |
| [frames-inline-header-normal-control](frames-inline-header-normal-control.png) | Pass | Pass |
| [frames-inline-header-overhang](frames-inline-header-overhang.png) | Fail | Pass |
| [frames-inline-header-overhang-normal-control](frames-inline-header-overhang-normal-control.png) | Pass | Pass |
| [frames-inline-header-separated](frames-inline-header-separated.png) | Fail | Pass |
| [frames-inline-header-separated-normal-control](frames-inline-header-separated-normal-control.png) | Pass | Pass |
| [frames-inline-header-table-clearance](frames-inline-header-table-clearance.png) | Fail | Pass |
| [frames-inline-header-table-clearance-normal-control](frames-inline-header-table-clearance-normal-control.png) | Pass | Pass |
| [frames-inline-page-end](frames-inline-page-end.png) | Fail | Pass |
| [frames-inline-page-end-normal-control](frames-inline-page-end-normal-control.png) | Pass | Pass |
