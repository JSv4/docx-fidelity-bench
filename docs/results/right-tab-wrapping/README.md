# Text following a right tab

These seventeen original Wren inputs cover Docxodus #1488. They exercise long tails,
mixed tab/text runs, a larger following font, expanded character spacing, wide glyphs,
multiple pages, VML textbox aliases, and a title that wraps before its tab.

The references were rendered with LibreOffice 25.8.7.3. Baseline captures use the public
HTML/PDF API from `ac4e6a329a2204d40cb00d3b753f1e35b8ddb528`, whose complete source tree
is identical to main `b3d6de066e0813a04777a179c05252b922196355`. Candidate captures use
the working tree recorded in `capture.json`; its changed source files and runtime asset
graph are hashed. These are local diagnostics, not production CI or a fresh Word reference.

All seventeen packages pass Open XML SDK 3.5.1 validation. Every LibreOffice reference
passes its mandatory PDF checks. Main fails the visible-token or end-marker checks in
eight cases and refuses the two wrapped-title reproducers; seven controls pass.
The fixed candidate passes all seventeen cases. All seven control page rasters are
byte-identical to main; PDF bytes and HTML bytes are not claimed identical.

The contract requires the complete source token inventory, declared fonts, page count,
physical page geometry and the final marker inside the text column or textbox. The
two-page case also requires its unique final marker on the reference's final page.
The short right-tail and wrapped-title short-tail controls additionally require their
final label within 1.25 pt of its native reference position, protecting the right stop.
The expanded-spacing case uses single-letter inventory labels, making the raw PDF
word inventory unambiguous even with six-point character spacing. The two dot-leader
controls use the existing source-validated policy that ignores only isolated decorative
dot tokens; their original PDF word geometry and raster remain available.

Each comparison sheet shows every page at 96 DPI and 100% scale: LibreOffice, main,
and the fixed export. A labeled panel states when no PDF or no additional page exists.
`capture.json` binds each input, source/runtime, public HTML/PDF output, inspected word
geometry, mandatory result, page raster and screenshot by SHA-256. Line-breaking and
tab-placement differences remain visible; complete output does not imply exact visual
equivalence to LibreOffice.

The seven controls are `left-control`, `center-control`, `long-prefix-control`,
`long-both-control`, `short-control`, `vml-rect-short-control`, and
`wrapped-short-control`. The other ten cases reproduce missing or rejected output on main.

## Production confirmation

The pinned production runs use benchmark commit
`46e4672d9802d5e6b2b2ac9da5d3556c31d4f0dc` and rebuild both exact renderer commits:
[main b3d6de06](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41211298822)
and [fix 5aaab582](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41211297080).
Both LibreOffice reference calibrations pass at 100. The fixed export passes all
17 mandatory cases; main passes 7, loses required content in 8, and refuses 2.
The aggregate diagnostic score rises from 35.6871 to 77.6089. None of the cases
meets the full visual close-match threshold. All seven control page PNGs and scores
are unchanged; PDF bytes and PageMap digests differ between renderer builds.

`production-evidence.json` binds the verified artifact ZIPs, exact source commits,
inputs, PDF outputs, PageMaps, references, calibrations and scores by SHA-256.
`production-screenshots.json` binds every panel in the seventeen
`production-*.png` comparison sheets to its artifact. Each sheet displays all
pages at 96 DPI and 100%, including the two-page case; missing outputs have labeled
panels. The linked Actions artifacts retain the underlying production results.
