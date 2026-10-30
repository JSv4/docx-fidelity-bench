# Atomic source content: focused results and previews

These ten original cases cover [Docxodus #1421](https://github.com/JSv4/Docxodus/issues/1421): an equation following a tab, a true two-reviewer consolidation of that equation and an independent suffix edit, discarded field-instruction text before an equation, an unfinished field holding a hyperlink/tab, and one drawing that supplies both an image and a textbox. Each has a control without the trigger.

The exact main baseline is `ca20684dda3504eeacf95d85025057a99da60246`; the candidate is `230030f9ace7c34f57f38aa5c29b612971c639a8`. Both adapters were built from verified clean source commits. Main fails all five reproducers and passes all five controls. The candidate and the independently authored calibration score 100 on all ten cases. These are focused diagnostics: only 10 of the 208 cases in `redline-v22` were measured, so no full-suite score is reported.

[The evidence record](evidence.json) preserves source/build identities, environment and metric contracts, original result digests and each mandatory check outcome. [Capture records](captures.json) bind every preview to the candidate DOCX, exported PDF and PNG by SHA-256. The screenshots were captured on October 30, 2026 UTC with LibreOffice 25.8.7.3: headless PDF export, first-page rasterization with `pdftoppm`, blank lower-page cropping and a generated label. They are review previews, not Word references or PDF fidelity scores.

| Case and LibreOffice preview | Main | Candidate | Authored |
| --- | ---: | ---: | ---: |
| [redline-tab-equation](redline-tab-equation.png) | 0 | 100 | 100 |
| [redline-tab-equation-consolidate](redline-tab-equation-consolidate.png) | 0 | 100 | 100 |
| [redline-tab-equation-control](redline-tab-equation-control.png) | 100 | 100 | 100 |
| [redline-tab-equation-consolidate-control](redline-tab-equation-consolidate-control.png) | 100 | 100 | 100 |
| [redline-field-source-text](redline-field-source-text.png) | 0 | 100 | 100 |
| [redline-field-source-text-control](redline-field-source-text-control.png) | 100 | 100 | 100 |
| [redline-captured-field-source](redline-captured-field-source.png) | 0 | 100 | 100 |
| [redline-captured-field-source-control](redline-captured-field-source-control.png) | 100 | 100 | 100 |
| [redline-shared-drawing-source](redline-shared-drawing-source.png) | 0 | 100 | 100 |
| [redline-shared-drawing-source-control](redline-shared-drawing-source-control.png) | 100 | 100 | 100 |

The independent markup resolver verifies complete accepted/rejected semantic views and selective reviewer results. The `inline-trees` assertion additionally verifies equation operators/properties, drawing structure, textbox content and related image bytes against the authored expectations. All new input and authored packages were independently checked with Open XML SDK 3.5.1 without findings, and all candidate outputs pass its no-new-errors gate. Negative tests reject altered operators, changed image bytes, missing textbox text and suffix churn. Equivalent adjacent math text runs are accepted.

LibreOffice's authored calibration supports only 5 of the 20 accept/reject views here. On the six equation cases (12 views), it keeps both whole-equation alternatives after either operation. On rejection of the unfinished field it loses the tab; on both resolutions of the whole drawing replacement it retains an extra empty paragraph. These specific views are declared ineligible, while independent markup, structure and SDK checks remain mandatory. The five eligible views all pass. The unfinished field's instruction-only contents are hidden in the LibreOffice preview; its retained source is measured in XML.

Word Online was separately checked during the core investigation and also retained both whole-equation alternatives after Reject All, including the space control. That check used an earlier focused reproducer, not these ten captured candidate packages. Desktop Word accept/reject behavior has not been validated. The core change restores proper whole-equation revision wrappers; it does not add fine-grained mathematical run revisions.
