# Bookmark gap between regrouped textboxes

Two unchanged Spruce textboxes originally have separate VML carriers and a point bookmark between them. The revision removes the bookmark, edits the tail, and combines both shapes into one carrier. The control keeps separate carriers while making the same bookmark and tail edits.

Historical main `785656a43737ba954fcab9319c3db03a50bc10a9`, before the carrier-identity fix, scores 0 on the reproducer and 100 on the control. Current main `9b230def8115dd0d0f187b6de2be0f90a4aac1d6`, which already includes [Docxodus #1477](https://github.com/JSv4/Docxodus/pull/1477), and the authored calibration score 100 on both. This benchmark pins an already-fixed defect; the accompanying product PR adds regression coverage only. These are focused 2/216 diagnostics, with no full-suite score.

Independent accepted/rejected views check the ordered text and named bookmark endpoints. Exact `w:pict` subtree assertions also check carrier multiplicity, geometry, and textbox bodies, so text equality cannot hide a regrouped source tree. Open XML SDK no-new-errors checks and the untracked closing line remain mandatory. The native control passes both LibreOffice text comparisons.

LibreOffice 25.8.7.3 retains an extra empty paragraph after both acceptance and rejection of the independently authored whole-paragraph reproducer. Initial calibration failures are preserved in [evidence.json](evidence.json); those two views alone are declared ineligible. Independent marker/order and exact carrier checks remain mandatory. No Word result is claimed.

[Evidence](evidence.json) retains run contracts, exact source/build identities, all check declarations/outcomes, and original result hashes; repeated observed subtree trees are omitted. [Capture metadata](captures.json) binds every preview to the measured DOCX and records PDF/PNG hashes. These are LibreOffice PDF exports rasterized with Poppler, with blank lower page space cropped and review labels added. Bookmarks are invisible in this renderer; the independent XML checks establish their positions.

| Case | Before carrier fix | Current main |
|---|---|---|
| Regrouped carrier | [Historical baseline](baseline-redline-textbox-marker-gap.png) | [Current main](candidate-redline-textbox-marker-gap.png) |
| Separate-carrier control | [Historical baseline](baseline-redline-textbox-marker-gap-control.png) | [Current main](candidate-redline-textbox-marker-gap-control.png) |

To reproduce, build an exact commit with `python3 -m bench redline build-docxodus --source CHECKOUT --commit FULL_SHA --out runs/build`, then run `python3 -m bench redline run --adapter docxodus --candidate FULL_SHA --build runs/build --validator runs/validator --case redline-textbox-marker-gap --case redline-textbox-marker-gap-control --out runs/result`. Use `--adapter authored --candidate authored-1428` without `--build` for calibration.

All 214 previous cases and their package bytes are unchanged. The Spruce text, literal shape markup, and expected redlines were authored independently in the benchmark generator, without importing the preserved product reproducer.
