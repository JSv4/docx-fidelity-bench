# Composed inline bookmark changes

Alice changes the prefix and adds or removes a bookmark around an unchanged tab. Bob independently changes the suffix; an unchanged equation sits beside the tab. Each reproducer has a control with the same text edits and unchanged bookmark presence.

Baseline `9b230def8115dd0d0f187b6de2be0f90a4aac1d6` scores 0 on both reproducers and 100 on both controls. Candidate `923a8688dc8872c4c110a67d3e3a5eb4464566b8` and the independently authored calibration score 100 on all four cases. These are focused diagnostics for 4 of 214 cases in `redline-v24`, with no full-suite score.

The independent markup resolver checks exact ordered inline content after accept-all, reject-all, and selective acceptance of Alice or Bob. This catches lost endpoints, misplaced ranges, and incorrect reviewer ownership. All eight LibreOffice text comparisons are eligible and pass calibration. Open XML SDK no-new-errors checks and unchanged-text assertions remain mandatory. No Word result is claimed.

The [complete evidence](evidence.json) retains run contracts, source/build identities, all check outcomes, and original result hashes. [Capture metadata](captures.json) binds each preview to the measured DOCX output and records PDF/PNG hashes. The previews are headless LibreOffice 25.8.7.3 PDF exports, rasterized with Poppler; the blank lower page is cropped and a review label added. Bookmarks are invisible in this visual renderer, so exact marker order and ownership are assessed by the independent XML checks above.

| Case | Main preview | Candidate preview |
|---|---|---|
| Addition | [Main](baseline-redline-composed-bookmark-add.png) | [Candidate](candidate-redline-composed-bookmark-add.png) |
| Addition control | [Main](baseline-redline-composed-bookmark-add-control.png) | [Candidate](candidate-redline-composed-bookmark-add-control.png) |
| Removal | [Main](baseline-redline-composed-bookmark-remove.png) | [Candidate](candidate-redline-composed-bookmark-remove.png) |
| Removal control | [Main](baseline-redline-composed-bookmark-remove-control.png) | [Candidate](candidate-redline-composed-bookmark-remove-control.png) |

Run `python3 -m bench redline build-docxodus --source CHECKOUT --commit FULL_SHA --out runs/build`, then `python3 -m bench redline run --adapter docxodus --candidate FULL_SHA --build runs/build --validator runs/validator --out runs/result` with `--case` for each of the four IDs above (the filenames without their stage prefix or extension). Use `--adapter authored --candidate authored-1426` without `--build` to calibrate.

All 210 previous cases and their package bytes are unchanged. The new Maple/Cedar text and literal OOXML were authored in the benchmark generator without importing product fixtures.
