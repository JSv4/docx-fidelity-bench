# TIFF and WMF image normalization

Ten original Poplar fixtures cover body/header PNG controls, equivalent TIFF pixels, and WMF
rectangle/ellipse outlines in ordinary, wide, tall, grouped and anisotropic-window placements.
They extend the PDF suite to `core-v86` / 578 cases. All 568 prior inputs and declarations are
unchanged except their generator digest; the redline suite is unchanged.

The local native-facade/Chromium diagnostic passes all ten candidate cases. Main
`1240cc5dc0586293cb937c59c973550027c31fda` fails all eight TIFF/WMF cases. Both PNG controls have
identical complete page rasters and scores before and after. Candidate source is
`0cb9566acf63ccaf1c0ebf16fea81b84a63342f4`; its native binary was built from the same correction
before commit. Production public WASM exports are recorded separately below.

Each image has independently colored blue rectangle and purple ellipse checks. The PNG/TIFF
bounds and paint coverage compare with LibreOffice; WMF checks use absolute geometry derived
from the original shape records and authored placement, adjudicated by fresh Word captures.
All retain 1.5pt bounds and 8% coverage limits. Missing, displaced or materially thinned/thickened
figures fail. Full-page raster scores continue to measure contour and unrelated differences.

| Cases | Purpose |
|---|---|
| Body/header PNG | Existing browser-decodable controls |
| Body/header TIFF | Same original pixels survive normalization |
| Body/header WMF | Both positive-width outlines survive conversion |
| Wide/tall WMF | Picture sizing stretches geometry and paint together |
| Group WMF | A VML coordinate group determines the final picture width |
| Anisotropic WMF | Window x scale 0.5 independently transforms both figures and their pens |

The anisotropic case keeps both figures within its window. An earlier unpublished probe used
a narrower window that legitimately clipped the ellipse; it was replaced so full-figure paint
assertions test the intended mapping behavior. No clipping tolerance or image assertion was
removed, and the finalized fixture still detects a uniform-x pen through paint coverage.

Fresh Word for the web PDFs of an independent five-image basis establish logical endpoint
exclusion `truncate(1 / scale)` and two-axis paint scaling. A fractional-size capture confirms
that physical viewport dimensions stay unrounded. The exact ordinary and anisotropic Poplar
WMF bytes were also captured through DrawingML carriers. The original VML carrier printed a
linked-image error in Word, so these are image-semantics diagnostics, not registered whole-page
Word references. Word substituted Times New Roman for Liberation Serif; no font-matched Word
page-fidelity claim is made. Native inputs/PDFs remain outside the source tree; hashes and
observations are retained in the evidence metadata.

LibreOffice 25.8.7.3 shifts the thick-pen ellipse and keeps a uniform outline during nonuniform
image sizing. The Word-adjudicated assertions bind every candidate; the existing provider
rule excludes them only from LibreOffice reference eligibility/calibration. Raw declared
checks are also retained for LibreOffice so its disagreement stays inspectable.

Every candidate local visual score is below the close-match threshold (77.90–90.82). LibreOffice paints
a default black VML frame absent from both main and candidate; the PNG controls retain this
existing discrepancy. Word/LibreOffice outline differences and small text-position differences
also remain. The results establish restored image content and the stated geometry contract,
not complete visual equivalence.

The ten labeled sheets show the top-left 270 by 330pt of each original page, at unchanged
96-DPI raster size, from LibreOffice, main and candidate. Labels are outside the page crops.
`local-evidence.json` binds inputs, PDF/HTML/bitmap hashes, checks, tools, fonts and sheets.
No PDF-byte or HTML-byte equivalence is claimed for controls. No external document content,
font programs or authentication material is included.

## Production export verification

[Candidate run 41192815098](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41192815098)
builds the public WASM/export packages from `0cb9566acf63ccaf1c0ebf16fea81b84a63342f4`.
[Main run 41192867714](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41192867714)
builds `1240cc5dc0586293cb937c59c973550027c31fda`. Both use benchmark source
`744582556b41e8574d6c3d91b643c2d88a67162b`, pinned Chromium 143 and the declared Liberation
Serif fonts. Both LibreOffice calibrations score 100 with all mandatory checks passing.

All ten candidate exports pass every mandatory check. Main fails all eight TIFF/WMF cases:
four produce PDFs with missing colored figures; four fail strict export with no PDF. Both
PNG controls retain identical complete page PNGs and identical scores. Their PDF bytes and
PageMap digests differ, so those forms of identity are not claimed.

| Production case | Candidate score | Main result |
|---|---:|---|
| Body PNG / TIFF | 90.8200 / 90.8200 | PNG unchanged; TIFF missing figures |
| Header PNG / TIFF | 90.8609 / 90.8609 | PNG unchanged; TIFF missing figures |
| Body WMF | 89.9146 | Export failed |
| Header WMF | 89.9597 | Missing figures |
| Wide / grouped WMF | 84.8445 / 84.8445 | Wide export failed; group missing figures |
| Tall WMF | 86.7403 | Export failed |
| Anisotropic WMF | 82.3175 | Export failed |

Every production score remains below the close-match threshold. The restored image geometry
does not remove the previously described LibreOffice frame and outline differences. The
`*-production.png` sheets show complete pages at 75% of their unmodified 96-DPI rasters, with
generated labels and explicit failure panels where main produced no PDF. All ten sheets are
attached to the paired PR. `production-evidence.json` binds run/artifact IDs, ZIP digests,
renderer commits, inputs, fonts/runtime metadata, PDF/raster/inspection hashes, checks, scores
and screenshot hashes. The exact raw artifacts remain downloadable from the linked runs.
