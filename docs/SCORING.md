# DOCX rendering fidelity scoring

This benchmark compares the PDF delivered by a renderer with an immutable reference PDF. It reports a layout similarity score, mandatory correctness checks, and measured coverage together. A high layout score alone does not prove correct text, links, color, reading order, or every DOCX feature. The first track uses LibreOffice; Word scores require separately registered Word captures.

The comparison (redline) track has its own contract: authored document pairs, accept/reject round trips through two independent engines, validity, and declared structural assertions. It is described in `docs/REDLINE.md` and is not part of the PDF suite score.

## Page measurements

Rasterize both PDFs with the same Poppler executable at 96 DPI using their physical CropBox. Compare pixels at their original positions. Do not align, resize, warp, remove content, or mask regions. Poppler sizes each raster from its own fractional page extent, so two pages whose physical boxes agree within the 0.25-point geometry tolerance can differ by one pixel. When each raster dimension differs by at most one pixel, place both rasters unchanged at their CropBox top-left origin on a white canvas of the larger width and height; the added edge is blank, and any ink there is still measured. Rasters that differ by more than one pixel in either dimension fail a mandatory check and score zero. The physical geometry check applies independently.

Ink is any pixel with at least one RGB channel below 231. Precision is the fraction of candidate ink pixels that have reference ink within one pixel horizontally, vertically, or diagonally. Recall is the fraction of reference ink pixels that have candidate ink within the same radius. The one-pixel radius is about 0.75 PDF points at 96 DPI.

Ink F1 is `2 × precision × recall / (precision + recall)`. If their sum is zero, F1 is zero. If one mask is empty and the other contains ink, F1 is zero. If both are empty, F1 is one. Blank pages still face page count and content checks.

SSIM uses luminance `0.2126 R + 0.7152 G + 0.0722 B`, non-overlapping 8 by 8 windows, smaller windows at page edges, population variance/covariance, C1 = 6.5025, and C2 = 58.5225. For each window, multiply `(2 μr μc + C1)` by `(2 covariance + C2)` and divide by `(μr² + μc² + C1) × (variance_r + variance_c + C2)`. Average window values by pixel count. Preserve the raw mean and clamp it to zero through one for scoring. The raster formula remains version 2; the complete scoring contract is version 3, implemented in `bench/metrics.py`.

The page score is `100 × min(SSIM, ink F1)`. Keep full precision in JSON and round only for display. For precision 0.96 and recall 0.90, F1 is 0.929032. If SSIM is 0.985, the page scores 92.90. This means the weaker similarity measure is approximately 0.929; it does not mean 92.90 percent of the document is correct.

## Cases and suites

A case uses its lowest page score. One bad page cannot be averaged away. Any mandatory failure makes the case score zero, even if most pixels match. Extra and missing pages remain in the union of page indices and score zero. Known conversion failures are measured candidate failures with zero scores. Missing references, invalid reference content/fonts, or broken measurement infrastructure are unmeasured.

Metric version 3 permits a case to declare `clippedTokens`: words wholly outside a source-proven clip,
with maximum authored counts. Such words may be absent from the PDF text layer or present whole.
A fragment, duplicate beyond its authored count, or any missing mandatory visible word fails.
The original source proof requires every occurrence to lie after enough explicitly exact-spaced paragraphs
to exceed an exact row height; mandatory and clipped inventories cannot overlap. The complete visible
inventory, optional counts, observed counts and raw PDF words remain evidence. This does not remove
ink from raster scoring or exempt ordinary body text. The declaration binds the suite digest; no
historical score is relabeled under the new contract.

Starting with `core-v77`, `bench/source_clipping.py` also proves two narrow fixed-textbox cases.
The box must have explicit positive geometry, zero insets, no rotation/effects, and fixed sizing:
DrawingML `noAutofit`, or a VML box with only numeric point width and height. Linked stories,
incoming VML links, conditional alternatives, relative sizing, explicit overflow, inherited raised
or hidden text and unsupported ancestry are rejected. Every paragraph has explicit zero margins
and exact line spacing; all runs request the pinned Liberation Serif family, use printable ASCII,
and have positive explicit font sizes no larger than the exact line. For a vertical clip, the
paragraph's minimum source offset must exceed the box height by **more than two font ems**.
Equality and partially exposed lines have no exemption. The four pinned font faces have global
glyph tops below 1.01 em; the larger separation is deliberately conservative. Font metrics and
independent boundary probes are recorded in the focused evidence, without copying font programs.

The second textbox proof admits an entire box far outside paper horizontally. It requires one
explicit, valid page section, a body-hosted nonwrapping anchor, horizontal margin and vertical
paragraph offsets, and the same fixed-box/story restrictions. A box is optional only if its
right edge plus the entire paper width is negative, or its left offset exceeds the entire paper
width. This bounds any valid margin origin without estimating paragraph height or placement.
Closer off-paper boxes, straddling boxes and unknown coordinate bases remain unsupported.
Every claimed word must occur only in the proven source region with its exact authored count.
Neither proof uses candidate geometry, warnings or success to decide what may be omitted.
The PDF token rules and unmodified full-page raster measurements remain the same; the new suite,
generator and inspector digests distinguish these source declarations from historical results.

Mandatory checks cover conversion, artifact digests, page count, physical MediaBox and CropBox coordinates within 0.25 PDF points, rotation, raster dimensions, the full visible token inventory including duplicate counts (visible text excludes the invisible Unicode bidirectional formatting controls U+061C, U+200E, U+200F and U+202A–U+202E, U+2066–U+2069; every other character, including letters, punctuation, soft hyphens and zero-width spaces, still counts unless the explicit decorative-leader policy below applies, and each normalized word keeps its raw extraction as evidence), declared font families, and each case's assertions. Physical box coordinates include UserUnit. Marker matching uses the same visible text and must be unique; ambiguity fails. Region assertion version 2 allows a declared 0.0001-point boundary tolerance for PDF coordinate serialization, about 0.000133 pixels at 96 DPI; version 1 retains exact boundaries. This does not shift or align rasters. Current assertions check named regions/page membership, markers sharing a page, and marker origins relative to the captured reference. The endnote origin uses 0.5-point tolerance and the reference page, so reference providers can use distinct endnote page layouts. An assertion marked `adjudicated: word` records layout measured in Word reference PDFs that LibreOffice does not follow. It binds every candidate and every Word reference. It does not bind a LibreOffice capture, either when deciding a LibreOffice reference's eligibility or when LibreOffice is measured against a LibreOffice track as calibration, so that track stays complete and its calibration stays at 100 while other candidates are held to Word's layout. On such a case, a candidate that follows Word is compared with LibreOffice pages that hold different lines, which caps its raster score there. Future link, reading order, precise baseline, and perceptual color assertions need explicit implementations and tests; they are not implied by this score.

An authored image case may add a version-1 `color-reference-geometry` or `color-geometry` assertion. It declares
one page and a non-gray RGB ink color on white. An independent 96-DPI Poppler raster scan
collects that ink's unshifted bounds in points and fractional pixel coverage, including
antialiasing. The three color channels must agree within 0.015 on the implied white-background
blend; coverage below 0.05 is ignored to exclude negligible fringes. Grayscale pixels are excluded before matching, so black text and its antialias fringe
do not qualify even for a nearly black declared ink. Unrelated colors are rejected. Both reference and candidate must have positive paint, their bounds
must agree within the declared point tolerance, and their coverage ratio must agree within
the declared fraction. The static-image cases use 1.5pt bounds tolerance (two raster pixels)
and 8% coverage tolerance; both are additional mandatory checks, with hard schema maxima of
2pt and 10%. They detect missing graphics, shifted/resized bounds and material pen-width loss.
They do not prove pixel-for-pixel shape identity: unchanged full-page raster scores still
measure all colors and contour differences. Source and inspector hashes bind this opt-in
contract; cases without it keep their existing checks.

The absolute `color-geometry` form declares positive `boundsPt` and `coverage` instead of
following the reference's paint. It is explicitly Word-adjudicated and uses the existing
provider rule above: candidates must satisfy it even when LibreOffice disagrees. The WMF
expectations come from the original shape coordinates, pen width and authored picture
placement. Native Word diagnostics establish device-pixel endpoint exclusion and scaling of
the complete outline; the exact original WMF bytes were also captured in a DrawingML carrier.
Rectangle stroke area is its centerline perimeter times pen width; ellipse perimeter uses
Ramanujan's approximation (exact for the circular cases and negligible error for the near-circle
anisotropic-window case), then scales to 96-DPI pixel coverage. Neither candidate output nor
LibreOffice geometry supplies these constants. The Word VML carrier failed to paint, so these
diagnostics adjudicate image semantics, not a registered whole-page Word reference. The 1.5pt
and 8% limits are unchanged. LibreOffice differences remain visible in full-page raster scores.

An authored case may opt into `pdfTextNormalization: "isolated-dot-leaders-v1"`. Source validation
requires dot-leader tab definitions and actual tab characters (`w:tab` or U+0009 in `w:t`/`w:delText`),
and rejects literal ASCII ellipses in Word-part XML text. Tabs in field instructions do not qualify. Only isolated extracted PDF words consisting of three or more
ASCII periods are then omitted from token counts. Glued content/leader words, short punctuation,
numbers and other words still count exactly. Every raw word and its coordinates remain intact;
ignored decorative words are retained in the token check's JSON evidence. PDFs, raster ink, page
geometry, marker coordinates and similarity thresholds are unchanged. The same policy applies to
reference and candidate inspection, and its declaration, version and inspector source hash bind the
measurement contract. A missing normalization identity fails a mandatory check. This accounts for
providers that paint leaders as text versus graphics without suppressing authored ellipses or
splitting words to invent marker positions.

Within each primary category, average case scores. Then average the category means equally. Two column cases scoring 99 and 97 give a column mean of 98. With a note case at 60 and a table case at 100, the suite scores 86.00. If note conversion fails, its zero remains in the denominator and the suite scores 66.00.

Publish a suite score only when every required case is eligible and has a classified candidate outcome. An absent reference does not become a zero score; it makes the suite incomplete and removes the headline score. Always display measured/required coverage, mandatory pass rate, close-match rate, and per-case evidence. Current partial category means are diagnostic only.

## Gates and reproducibility

A close match needs every mandatory check and, on every page, SSIM at least 0.98 and ink F1 at least 0.95. These are initial engineering targets, not calibrated perceptual guarantees. Report-only mode permits complete runs with known rendering failures. Mandatory and close gates enforce their additional conditions. Every mode fails on incomplete coverage.

Regression comparison requires an unchanged measurement contract: metric version, suite and input/generator digests, immutable reference bundle, PDF utilities and hashes, font files, adapter identity, and candidate runtime. Candidate source commits may differ. A changed reference provider creates a separate track. Reuse the same registered reference bundle to compare candidate versions; regenerated PDF metadata can change bundle identity.

Before enabling a release gate, measure repeated reference and candidate exports and deliberate errors. The automated calibration tests cover identical images, blank/missing ink, shifted ink, threshold boundaries, changed colors, missing pages, duplicate text, ambiguous markers, wrong fonts, changed page units, stale identities, and incomplete coverage. Compare identical-engine exports as an integration check. Noise tolerances require review of repeated measurements; they are never chosen to make a desired candidate pass.

A regression record proposal requires a complete, intact result and the current suite. It writes a new proposal and does not refresh records automatically. Review paired images, overlays, PDFs, diagnostics, and environment identities before accepting one. A regression pass can coexist with visible differences; preserve those differences in the report.

## Delivered HTML feature checks

Some rendering defects concern a delivered HTML tooltip or scrollable comment rather than printed ink. A case may
therefore declare separately versioned `htmlAssertions` in addition to its PDF assertions. The
harness checks the delivered standalone HTML, not the renderer's internal diagnostics. The source
artifact digest, inspector version/source hash and exact declarations are retained in the run contract.

These checks do not alter PDF raster measurements, PDF case scores, category means or reference
eligibility. Reports show a separate HTML coverage/pass summary. Missing or mismatched artifacts
are unmeasured HTML observations; an observed wrong attribute or inaccessible declared paragraph is a measured feature failure.
`--gate report` requires complete declared HTML coverage as well as complete PDF coverage;
`mandatory` and `close` also require the HTML checks to pass. Regression comparison refuses
unmeasured HTML coverage and flags an observed HTML failure even when the PDF score stays 100.
Record proposals require complete declared coverage. Reference-engine calibration checks only its
PDF artifacts and does not claim to validate another renderer's HTML metadata.

HTML feature checks assert the fixture's explicit delivery contract. They are not a Word PDF-fidelity score.

Version 1 `marker-readable` requires the complete authored paragraph in order and its unique final token to be visible after user-accessible scrolling. Actual range rectangles, clipping ancestors and overflow modes come from a separate offline browser context with scripts disabled; the inspector recomputes pass/fail and verifies the HTML, observer and browser executable hashes. A distinct full `htmlProfile`, when declared, is bound separately from the PDF profile. These checks make no claim that a static PDF prints all scrollable comment text, or that every word has been compared as pixels.

Version 1 `marker-computed-style` adds exact computed `font-size` checks for unique HTML markers.
Every visible inline fragment of the marker must have the declared pixel size, and the marker must
have positive, accessible geometry under the same clipping policy as readability assertions. Mixed
styles cannot pass by reporting only the first fragment. These checks remain separate from PDF scores.
