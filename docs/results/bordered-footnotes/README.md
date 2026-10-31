# Bordered footnote continuations

Thirteen original Ash cases cover long box/bottom-bordered paragraphs, subsequent continuation
pages, kept paragraphs, headings kept with their successors, and one-cell footnote tables.
Plain, separate-paragraph, short, kept, heading and table controls accompany the reproducers.
All packages validate with Open XML SDK 3.5.1. The preceding 620 inputs and contracts remain
unchanged except the shared generator hash; `core-v91` contains 633 cases.

Current main `06921d9505fdb8c0541d4f8c93ed8939296c521e` refuses the seven bordered overflow
cases. The fixed runtime `0875eab87ecaf0af716af7c585f9745d159c4a95` exports all thirteen with
complete source inventories. All six fitting/plain control sets retain byte-identical page PNGs.
The main capture uses the identical source tree/runtime from `cd446c19bf6b13aab0726451f50412c4c84d55c4`.

These local captures use strict fonts, explicit Liberation Serif files and a caller-owned,
sandboxed Chromium 143.0.7499.4. Reports identify that runtime as `browserObserved`.
Production owned-process measurements are recorded below. No fresh Word reference or exact native
layout parity is claimed. The existing border convention leaves the border open at internal
page breaks and retains the side borders.

| Cases | Main | Fixed | Native LibreOffice 25.8.7.3 |
| --- | --- | --- | --- |
| Box/bottom, 70 lines | Refused | Complete, two pages | Complete, two pages |
| Box/bottom, 100 lines | Refused | Complete, three pages | Complete, three pages |
| Box with kept 100-line paragraph | Refused | Complete, four pages | Complete, four pages |
| Box with kept heading | Refused | Complete, three pages | Complete, three pages |
| Box inside 100-line table cell | Refused | Complete, three pages | Incomplete; reference ineligible |
| Six controls | Complete | Identical page rasters | Five eligible; table control ineligible |

The two table cases retain their complete mandatory source-token contracts. LibreOffice emits
only one of their 100 note labels, and the unchanged reference-eligibility check rejects both
captures for missing source words. They are **reference-ineligible and unscored**, pending valid
native references. Their incomplete native pages and successful candidate output are retained
below as diagnostics. They are excluded explicitly from the **11-case diagnostic production suite**, not accepted as passing references or assigned a layout score of zero.
The eleven eligible local comparisons pass all correctness checks with the fix; main passes
five controls and refuses six reproducers. This is not full thirteen-case fidelity validation.

[Local PDF, input, runtime and screenshot bindings](local-evidence.json) record every check and
the exact eleven-case production selection. [SDK validation](source-sdk-validation.json) binds
each package hash to its findings. Every screenshot uses all actual PDF pages at 96 DPI and 100%,
without cropping or resampling; refusal and absent-page panels are labeled. The 13 sheets
contain 81 actual page panels.

![Box 70](notes-bordered-flow-box-70.png)

![Bottom 70](notes-bordered-flow-bottom-70.png)

![Box 100](notes-bordered-flow-box-100.png)

![Bottom 100](notes-bordered-flow-bottom-100.png)

![Plain control](notes-bordered-flow-plain-control.png)

![Paragraphs control](notes-bordered-flow-paragraphs-control.png)

![Short control](notes-bordered-flow-short-control.png)

![Kept box](notes-bordered-flow-box-kept.png)

![Kept plain control](notes-bordered-flow-plain-kept-control.png)

![Heading box](notes-bordered-flow-box-heading.png)

![Heading plain control](notes-bordered-flow-plain-heading-control.png)

![Table box — reference ineligible](notes-bordered-flow-box-table.png)

![Table plain control — reference ineligible](notes-bordered-flow-plain-table-control.png)

## Production validation

[Candidate run41221180196](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41221180196)
and [main run41221181974](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41221181974)
built the exact renderer commits at benchmark commit
`61e4619be3555e3184074d8e82bcc544e150f73f`. Both reference calibrations score100.
The candidate passes every mandatory check in all11 eligible cases; main passes the five
controls and refuses the six bordered overflow cases. All five production control page-PNG
sets and scores are unchanged. The raw layout score is77.1645425378445 for the candidate and
42.247961972003274 for main. Border painting and line positions still differ from LibreOffice;
only the short control reaches the close-match threshold. Completeness does not establish native
layout parity, and the two table cases remain reference-ineligible and unscored.

[Production evidence](production-evidence.json) binds the verified artifact ZIPs, exact inputs,
renderer builds, owned sandboxed Chromium143.0.7499.4, PDF/PNG files, page-map digests, checks
and scores. The11 sheets below include all70 actual PDF page panels at96DPI and100%, with
17 refused-page panels labeled; no page is cropped or resampled.

![notes-bordered-flow-box-70 — production](production-notes-bordered-flow-box-70.png)

![notes-bordered-flow-bottom-70 — production](production-notes-bordered-flow-bottom-70.png)

![notes-bordered-flow-box-100 — production](production-notes-bordered-flow-box-100.png)

![notes-bordered-flow-bottom-100 — production](production-notes-bordered-flow-bottom-100.png)

![notes-bordered-flow-plain-control — production](production-notes-bordered-flow-plain-control.png)

![notes-bordered-flow-paragraphs-control — production](production-notes-bordered-flow-paragraphs-control.png)

![notes-bordered-flow-short-control — production](production-notes-bordered-flow-short-control.png)

![notes-bordered-flow-box-kept — production](production-notes-bordered-flow-box-kept.png)

![notes-bordered-flow-plain-kept-control — production](production-notes-bordered-flow-plain-kept-control.png)

![notes-bordered-flow-box-heading — production](production-notes-bordered-flow-box-heading.png)

![notes-bordered-flow-plain-heading-control — production](production-notes-bordered-flow-plain-heading-control.png)
