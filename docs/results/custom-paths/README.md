# Literal custom paths

Eleven original Willow fixtures exercise DrawingML custom paths for
[Docxodus #1554](https://github.com/JSv4/Docxodus/issues/1554). They use independently
chosen labels, coordinates, dimensions and colors; no renderer fixture or helper is imported.
The suite covers polygons, quadratic and cubic curves, open strokes, two independently scaled
paths, both hole windings, reflections, translated group coordinates, an invisible shape and
a preset rectangle control.

The baseline is `643357cda97027b16260b3ba20ff85ef59eb7406`, whose complete tree equals
main merge `81f99d8b7898ef620a52b344e7f86281f4356d74`. The candidate is
`6a65f2cd8ec33d76008fec6abd0a843e2707094e`. Both public captures use their source-bound
production builds, strict verified Liberation Serif fonts, final review and hidden comments.
LibreOffice 25.8.7.3 provides the native references. Borrowed system Chromium is an unscored
public-API diagnostic, not the benchmark's pinned-runtime qualification or a Word parity claim.

`Compose.py` binds the source inputs, schema findings, declared profiles, native bundle,
renderer commits/trees, build files, runtime assets, capture manifests, reports and PDFs by hash.
It checks complete visible labels, dark ink under every source label, physical page bounds,
color bounds/coverage and source-positioned paint probes. The invisible control additionally
requires its complete authored frame to contain no ink. Every new case has a full-page review
sheet with baseline, native and candidate panels.

`MutateCurve.py` shifts a quadratic curve's control point while keeping its endpoints,
paint bounds, area and text. The resulting `wrong-curve.pdf` passes the existing mandatory
metrics but fails two supplementary paint probes. These probes add curvature discrimination
without changing scoring thresholds or normalizing candidate images.

Compound paths use even/odd fill based on both native hole experiments. The relevant
[ECMA-376 path definitions](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
do not prescribe a winding rule, while
[Apache POI's path implementation](https://github.com/apache/poi/blob/519e0a3c3945364e8ea75c172fe1a15fb6d4a202/poi-ooxml/src/main/java/org/apache/poi/xslf/draw/geom/XSLFPath.java#L58)
uses Java's nonzero default. Word behavior remains unverified; the same-winding fixture is a
retained discriminator for later adjudication. The group includes a transparent rectangle
spanning its declared child coordinate space because LibreOffice otherwise fits occupied bounds.

Reproduction from a provisioned checkout:

```sh
python3 -m bench.fixtures
python3 -m bench reference libreoffice --manifest runs/custom-paths-v2/manifest.json --out runs/custom-paths-v2/reference
node docs/results/export-reliability/Capture.mjs SOURCE runs/custom-paths-v2/manifest.json OUTPUT runs/custom-paths-v2/environment.json
python3 docs/results/custom-paths/MutateCurve.py runs/custom-paths-v2/reference/custom-path-quadratic/reference.pdf
python3 docs/results/custom-paths/Compose.py runs/custom-paths-v2 BASELINE_SOURCE CANDIDATE_SOURCE
```

Results: baseline **1/11**, candidate **11/11**; all eleven native references are eligible.
The 33 PDFs contain 33 pages and 108 checked visible labels (99 source labels plus nine
baseline placeholder labels). All 183 supplementary paint checks have their expected outcomes.
The wrong-curve control passes existing metrics and fails exactly two of its five paint probes.

The retained evidence is in `evidence.json` and the compressed inspections, reports and native
bundle beside it. Full input fixtures live under `fixtures/custom-path-*.docx`.
