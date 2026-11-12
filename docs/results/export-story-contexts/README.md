# Export reliability: positioned stories, tabs and clipping policy

Thirty-seven independently authored Jasper documents extend the PDF track to `core-v77`
(533 cases). All 496 preceding DOCX packages remain byte-identical. Their complete case
records are unchanged except for the shared generator digest. The fixtures are independently
authored and use generated graphics; font programs remain external.

| Renderer revision | Delivered PDFs | Independent PDF checks passing |
|---|---:|---:|
| Original baseline [`a72aac79`](https://github.com/JSv4/Docxodus/commit/a72aac79858321ed64cdc850c2e66f4b4de59153) | 25 / 37 | 17 / 37 |
| Intermediate [`cc57539f`](https://github.com/JSv4/Docxodus/commit/cc57539ff062dd6350c31792fa205177a7cc3a01), picture-wrap inputs only | 3 / 3 | 2 / 3 |
| Final candidate [`a5ae28c8`](https://github.com/JSv4/Docxodus/commit/a5ae28c88617f5c405ce575d5f8b10f828d8b6c9) | 37 / 37 | 37 / 37 |

All ten separate warning/strict-policy checks pass. The baseline delivers eight PDFs that fail
their independent checks: two single-run tab layouts miss their marker regions, the continued
linked story and four long-prefix textbox cases lose tokens, and the nonwrapping image marker
occupies the wrong region. Export completion alone therefore does not establish correctness.

These are **unscored public-API diagnostics**. The host is `ENVIRONMENT_INELIGIBLE` for
the benchmark adapter's pinned Chromium because its required user namespaces are denied.
The captures use separately provisioned system Chrome with its sandbox enabled, strict fonts
and exact source-bound builds. No sandbox restriction was disabled. There is no candidate
fidelity score, full-suite result or claim of Word parity.

The PDF inspector checks complete authored token counts, declared font families, finite page
geometry and source marker assertions. It does not compare candidate page counts, line positions
or pixels against LibreOffice. The labeled sheets show every page at its original 96-DPI scale;
failure panels identify exports that delivered no PDF. `InspectFonts.py` additionally binds every
delivered production report to the actual four configured TTF file hashes, resolved family,
exact face match, verified status and complete glyph coverage. The font programs remain external.

| Authored trigger and controls | Product change |
|---|---|
| Four positioned VML panels in one outer paragraph / fitting inline panel | [#1462](https://github.com/JSv4/Docxodus/pull/1462) |
| DrawingML/VML nested tab/text runs stored separately, mixed, or in one run | [#1465](https://github.com/JSv4/Docxodus/pull/1465) |
| Page-positioned legacy oval/rectangle fallback / fitting inline fallback | [#1466](https://github.com/JSv4/Docxodus/pull/1466) |
| Oversized top-and-bottom wrap clearance / fitting clearance, both stacking orders | [#1467](https://github.com/JSv4/Docxodus/pull/1467) |
| Long prefix before a textbox tab / short prefix and equivalent content-width insets | [#1468](https://github.com/JSv4/Docxodus/pull/1468) |
| Behind-text square wrapping / front square wrapping and behind-text nonwrapping | [Corrected #1444](https://github.com/JSv4/Docxodus/pull/1444) |
| One story continuing into a second unequal WPS frame / fitting linked and taller unlinked controls | [Frozen linked-flow implementation](https://github.com/JSv4/Docxodus/commit/a5ae28c88617f5c405ce575d5f8b10f828d8b6c9) |
| Whole paragraphs deliberately below a fixed clip / taller DrawingML and VML controls | [Frozen source-clipping implementation](https://github.com/JSv4/Docxodus/commit/a5ae28c88617f5c405ce575d5f8b10f828d8b6c9) |
| Entire fixed margin/paragraph textbox far outside paper / same on-paper box | [Frozen placement implementation](https://github.com/JSv4/Docxodus/commit/a5ae28c88617f5c405ce575d5f8b10f828d8b6c9) |
| Inline box raised into the paper margin by its containing run / unraised box | [Frozen raised-box implementation](https://github.com/JSv4/Docxodus/commit/a5ae28c88617f5c405ce575d5f8b10f828d8b6c9) |

The three picture sheets retain a controlled composition regression. The original a72 baseline
passes both square-wrap marker assertions. The cc575 intermediate passes the front square case
but puts the behind-text square marker inside the image region; the nonwrapping control passes.
This is a regression introduced during composition, not an original a72 square-wrap defect.
The intermediate capture uses the exact same three input packages and all the same assertions;
only its historical shared generator hash differs. The compositor verifies all other fields
before combining the evidence.

LibreOffice supplies 33 eligible references. The four legacy leaf references paint actual ovals/rectangles instead of the explicitly authored
`[SHAPE]` fallback labels. They remain **ineligible** under the token contract and are retained
visibly as such. These cases test fallback preservation and authored placement, not vector-shape
rendering fidelity. LibreOffice also positions the first short linked-frame outline below its
story text. Its complete token inventory does not establish frame-geometry correctness or Word
parity. The short VML clipping reference also shifts text downward and partially clips its third
mandatory line, although that complete word remains in its PDF text layer. The candidate paints
all three mandatory lines completely. The taller VML control is intact. Eligibility is not a
claim of complete ink or correct geometry. Different text insets, baseline positions and line
endings remain visible between renderers; the short textbox-tab controls keep their original
suffix-on-next-line behavior, while LibreOffice places the suffix on the first line.

`story-geometry.json` independently measures all five rows of all six nested-tab variants. The
authored column advances are 100pt and 210pt; the first-row regions are also ordinary manifest
assertions. The raised-box pair uses an authored 18pt lift and checks the body receipt position.
A predeclared 0.75pt tolerance permits one CSS pixel of print rounding; numerical observations
are retained rather than described as exact. All six tab variants pass their five-row checks.
The candidate's raised label moves 18.749999pt and its body receipt moves 0pt.
`bitmap-inventory.json` separately records one
complete generated bitmap entry in each of the three picture-wrap inputs.

Every page of all 37 sheets was visually reviewed. In the oversized-clearance fallback, the
front-stacked opaque rectangle covers most body label ink in both candidate and LibreOffice,
although whole words remain in the PDF text layer. This is the explicitly warned exclusion
relaxation, and strict policy rejects it. The candidate's behind-text variant paints both labels
above the rectangle; LibreOffice still covers them. Fitting controls keep text below the shape.
`clearance-geometry.json` checks all four rectangles' authored origin and dimensions using
unchanged raster fill bounds; this checks retained geometry, not unobscured text or parity.

## Source-only optional-token proof

The `clippedTokens` rule continues to retain the entire source inventory and all raw PDF words.
Only complete optional words may be absent or appear up to their authored count. A partial word,
extra occurrence, or missing mandatory visible word fails. Raster scoring, when an eligible
runtime/reference is available, still measures every pixel; there is no image masking.

This batch extends source validation with a deliberately narrow fixed-box proof. It requires
positive explicit dimensions, zero insets, known fixed sizing, no links or conditional alternatives,
and simple exact-line paragraphs with explicit zero margins. Every run requests Liberation Serif
and printable ASCII at a positive size no greater than its exact line height. Vertical omission
requires the paragraph's minimum source offset to be **more than two font ems below the clip**.
The authored source has three visible 12pt lines, two blank 12pt spacers, then its final 10pt text
at offset 60pt. A 36pt clip leaves a 24pt gap; the paired 84pt box preserves every line.

`ProbeClipBoundary.py` independently reads the four pinned TrueType files' `head` and `hhea`
tables without copying any font bytes. Global glyph tops are 0.981445, 1.007813, 0.980957 and
0.980957 em for regular, bold, italic and bold italic. Six original Quartz boundary probes at
different font/line sizes produced **zero** red-tail pixels in 600-DPI LibreOffice rasters.
That observation does not prove safety for arbitrary fonts or text. The proof therefore keeps
the narrower pinned-family/ASCII scope and greater-than-two-em guard. Equality, partial exposure,
larger fonts, theme substitution, non-ASCII text and moving the claimed token into the visible
region are rejected by independent negative mutations. The diagnostic PDF text layers may retain
whole clipped tail words even when no tail ink is painted; those raw observations are preserved.

The off-paper proof shares fixed-box and paragraph eligibility. It additionally requires one
explicit valid page section and a direct body-hosted nonwrapping anchor with horizontal margin
and vertical paragraph coordinates. Its conservative horizontal test bounds any margin origin:
the box's right edge plus the full paper width must remain negative, or its left offset must exceed
the full paper width. It makes no estimate of paragraph height. On-paper, straddling, equality,
unknown-basis, relative-size, overflow, autofit, shadow, multi-section and linked mutations fail.
Every occurrence of an optional word must be accounted for in the proven source region; an
additional visible-body occurrence rejects the declaration. Candidate warnings or geometry can
never make a word optional.

The fourteen focused contract tests cover positive cases and these negative mutations in both
supported dialects. The detailed public scoring contract is [SCORING.md](../../SCORING.md).

## Warning and strict-policy checks

`Policy.mjs` rerenders ten explicitly declared cases from `policy-contract.json`. It verifies
exact source/tree/build assets, manifest and input hashes, default report hashes, configured font
files and report faces, and the same sandboxed browser identity as the default capture.
Default warning codes and counts must match exactly. The oversized-clearance cases expect one
`drawing_clearance_relaxed` warning; clipped final paragraphs expect one `source_text_clipped`
warning; the off-paper two-paragraph story expects two. Their fitting/visible controls expect none.
Strict policy must reject those warned cases with `resource_policy_failure` in
`output_verification`, while their controls must deliver PDFs. This is a separate public-API
policy diagnostic, not a scoring exemption.

The first capture used page-relative coordinates for four clearance fixtures. That source also
has an independently unsupported continuous-flow placement approximation, so all four strict
exports rejected earlier at `docx_conversion`; fitting controls did not isolate the intended
clearance rule. `prequalification-policy-v2.json` and its exact manifest retain that failed
qualification. Only those four unpublished fixtures were corrected: horizontal page/12pt and
vertical page/18pt became horizontal column/2pt and vertical paragraph/0pt. Shape sizes, colors,
stacking, labels and all other package content remained unchanged. The final four-case baseline,
candidate, LibreOffice and strict-policy captures now isolate the clearance feature.

`MergeEvidence.py` composes those four corrected cases with the 33 byte-identical cases. It
compares every case field including the generator path; only the shared generator SHA may
differ. Source/tree/build/browser/font identities must match between segments, and every PDF
and default report hash is reread. Delivered strict PDFs are also reread, verified and copied;
warning and strict pass flags are recomputed from the selected reports and outcomes. The
composition is explicitly labeled diagnostic evidence, not a newly registered benchmark run.
`composition.json` preserves segment hashes. Six negative mutations reject changed case fields,
source identity, PDF digest, generator path, and missing or changed strict PDFs.

## Reproduction and source identities

The final candidate's tracked tree is `eab4aa9cd1d154bdd708dc42abf3fa879a789c90`.
Its official build receipt SHA-256 is
`12f73c17b3a84c254a3fb6ddaf07e75fdb7f2c3f652c3444d99b4be73c3c6a8e`.
The source is publicly fetchable:

```sh
git fetch https://github.com/JSv4/Docxodus.git review/export-reliability-a5ae
git fetch https://github.com/JSv4/Docxodus.git review/export-reliability-cc575
```

Build each exact checkout using `python3 -m bench build-docxodus --source SOURCE --commit FULL_SHA`.
Provision the declared fonts and tools separately. From this benchmark checkout, capture the
focused immutable manifest through the public API, preserving distinct output directories:

```sh
DOCXODUS_CHROMIUM_PATH=/opt/google/chrome/chrome TMPDIR=/tmp/dx-fragments \
  node docs/results/export-story-contexts/Capture.mjs SOURCE \
  docs/results/export-story-contexts/focused-manifest.json OUTPUT ENVIRONMENT_JSON
python3 docs/results/export-story-contexts/Inspect.py \
  docs/results/export-story-contexts/focused-manifest.json OUTPUT/capture.json
python3 -m bench reference libreoffice \
  --manifest docs/results/export-story-contexts/focused-manifest.json --out REFERENCES
node docs/results/export-story-contexts/Policy.mjs SOURCE \
  docs/results/export-story-contexts/focused-manifest.json OUTPUT ENVIRONMENT_JSON \
  docs/results/export-story-contexts/policy-contract.json POLICY_JSON
python3 docs/results/export-story-contexts/InspectFonts.py ENVIRONMENT_JSON BASELINE CANDIDATE
python3 docs/results/export-story-contexts/InspectStories.py BASELINE CANDIDATE
python3 docs/results/export-story-contexts/InspectPictures.py BASELINE CANDIDATE
python3 docs/results/export-story-contexts/InspectClearance.py CANDIDATE
python3 docs/results/export-story-contexts/Compose.py \
  docs/results/export-story-contexts/focused-manifest.json REFERENCES BASELINE CANDIDATE INTERMEDIATE
```

`capture.json` binds source trees, receipts, browser/font identities, input/PDF/report hashes,
raw raster hashes and all 37 review sheets. `font-bindings.json`, `story-geometry.json`,
`bitmap-inventory.json`, `policy-results.json`, `clip-boundary-probe.json` and the visual review
retain their separate diagnostics. References and raw run bundles stay in ignored directories;
the committed sheets and source/hash records make the stated scope reviewable without claiming
an unavailable fidelity score.

Validation: 388 Python contract tests and four Node adapter tests pass. The final registry
validates 533 inputs. The 14 focused clipping tests and six composition-tamper checks protect
the narrow source and evidence rules. The final provenance audit regenerates every historical
and new package and verifies its exact rights/source inventory.
