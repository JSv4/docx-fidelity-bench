# Export reliability: inline contexts and continued layout

Forty independently authored Flint inputs extend the PDF track to `core-v76` (496 cases).
All 456 previous DOCX inputs remain byte-identical; their case records change only the
required shared generator hash. No product fixture, helper or document content is imported.

| Renderer revision | Delivered PDFs | Independent checks passing |
|---|---:|---:|
| Original baseline [`a72aac79`](https://github.com/JSv4/Docxodus/commit/a72aac79858321ed64cdc850c2e66f4b4de59153) | 23 / 40 | 21 / 40 |
| Intermediate [`a42fc20a`](https://github.com/JSv4/Docxodus/commit/a42fc20aa1da5360c15539322041eed389ac6cf4) | 40 / 40 | 39 / 40 |
| Final candidate [`cc57539f`](https://github.com/JSv4/Docxodus/commit/cc57539ff062dd6350c31792fa205177a7cc3a01) | 40 / 40 | 40 / 40 |

The two additional baseline inspection failures are exact-line textbox PDFs missing their first
line. The a42 intermediate preserves that content but reveals a different failure: promoted
undecodable-image fallback text uses Arial instead of the declared Liberation Serif. Its
independent font check fails even though export succeeds. `intermediate-a42.json` retains that
result and its [font-failure sheet](intermediate-a42-header-image-undecodable.png); the input
and font contract remain unchanged for the final capture.

These are **unscored public-API diagnostics**. This host remains `ENVIRONMENT_INELIGIBLE`
for the benchmark adapter's pinned Chromium because its required user namespaces are denied.
Captures use a separately provisioned system Chrome with its sandbox enabled, exact
source-bound WASM/JavaScript builds, strict fonts and a hashed font directory. No sandbox
restriction was disabled. There is no registered candidate score, full-suite result or claim
of Word parity.

The independent PDF checks inspect the complete declared token inventory, fonts, finite page
geometry and source assertions. They do not compare candidate page counts, line positions or
pixels with LibreOffice. The screenshots show every page at its original 96-DPI size. An error
panel records any renderer that delivered no PDF.

The two image-identity sheets also show intermediate
[`ca99ac182a38409d06a516a4e61347fca878d7df`](https://github.com/JSv4/Docxodus/commit/ca99ac182a38409d06a516a4e61347fca878d7df).
That capture is deliberately limited to the same two input bytes and case assertions. The
original a72 baseline exports the intentionally undecodable repeated-header image and its
decodable control. The intermediate revision fails the undecodable case after promotion,
incorrectly reporting two newly broken images; its decodable control passes. This is a
composition regression, not an a72 conversion failure. The intermediate manifest retains its
historical generator hash; subsequent generator additions changed neither input bytes nor
assertions. The compositor compares every other case field before combining its evidence.

LibreOffice produced 37 eligible references. Three remain **ineligible** under the declared
contracts: the undecodable-image case prints a different fallback, and both VML-oval cases
paint actual ovals instead of the authored `[SHAPE]` fallback labels. Those screenshots are
retained and labeled. The oval cases test Docxodus placeholder preservation and continuation,
not oval-rendering fidelity. The undecodable part contains an original UTF-8 placeholder
explicitly declared as image/png; its short `FI` alternate label is counted twice for the two
header instances. A generated PNG supplies the ordinary image control. Known warning policy
is retained, and the final capture records warning codes rather than claiming the invalid
image became decodable.

Every a42 sheet was visually reviewed, including every page of the longer cases. All continued
paragraph/table labels and receipts are present. The oversized floats paint their complete
bitmap within the candidate page; their fitting controls remain visually stable. LibreOffice
clips the oversized float bitmap at the paper edges despite passing the text/font eligibility
checks. Eligibility therefore does not imply a complete or geometrically correct reference
image, and no image-fidelity conclusion is drawn from that reference.

The empty-tab case retains its text but paints no dotted leader, whereas LibreOffice does.
Inspection before and after pagination found the same positive-width tab carrier with no
border paint; this remains a converter limitation and is not evidence of leader preservation.
The separate nonempty tab-segment cases do paint their leader and preserve their complete
line inventory. The placeholder/image case preserves four authored fallback labels on its
first page and one complete bitmap on the continuation; the fitting control is unchanged.

All eight a42 textbox outputs contain all four inner lines. Across the four host-spacing pairs,
inner-line advances agree within 0.75pt; exact-inner advances satisfy the authored 14pt value
within that same print-rounding tolerance. Host receipt positions, reference text insets, some
line endings, table offsets, footnote separator weight and vertical gaps below wrapped rules
still differ between renderers. These results establish the stated content/continuation and
spacing checks, not pixel parity.

Final `cc57539f` page rasters are byte-identical to a42 for 39 cases. Only the two pages of the
undecodable-image case changed; both were reviewed again. Their `FI` fallbacks and body labels
remain visible, and the PDF now embeds only Liberation Serif. All 40 independent checks pass
without changing an input or relaxing the font contract. `visual-review.json` records the
complete intermediate review and exact final raster comparison. All four candidate textbox
pairs and all seven candidate bitmap inventories retain their stated checks.

| Original mechanism and controls | Product change |
|---|---|
| Oversized square/tight floating pictures / ordinary-size same-wrap pictures | [Docxodus #1450](https://github.com/JSv4/Docxodus/pull/1450) |
| Long automatically spaced paragraph, including citation / exact-line spacing | [#1451](https://github.com/JSv4/Docxodus/pull/1451) |
| Empty tab after wrapping prose / exact-line no-tab paragraph | [#1455](https://github.com/JSv4/Docxodus/pull/1455) |
| Leading table bookmark / unbookmarked long table | [#1456](https://github.com/JSv4/Docxodus/pull/1456) |
| DrawingML/VML natural and exact textbox lines / single and triple host spacing | [#1457](https://github.com/JSv4/Docxodus/pull/1457) |
| Oversized connected merges with horizontal span / fitting and unmerged grids | [#1458](https://github.com/JSv4/Docxodus/pull/1458) |
| Inherited empty/wrap-only frame / ordinary flow and directly positioned frame | [#1459](https://github.com/JSv4/Docxodus/pull/1459) |
| Impossible row/line/next/widow keeps / fitting-kept and long-unkept cell paragraphs | [#1460](https://github.com/JSv4/Docxodus/pull/1460) |
| Undecodable repeated-header image / decodable generated PNG | [#1461](https://github.com/JSv4/Docxodus/pull/1461), plus the [inherited-presentation correction](https://github.com/JSv4/Docxodus/commit/2fae23b89736435d51431b64171e3c069e99ac4d) |
| Encoded negative anchor/override wrap clearance / direct signed and positive clearance | [#1463](https://github.com/JSv4/Docxodus/pull/1463) |
| Nonempty manual-tab segment and shape-placeholder/image composition / fitting and ordinary controls | [Whole-inline-atom source](https://github.com/JSv4/Docxodus/commit/d287fc99436e0fc783e37440b45a8f2895743618) |

The long unkept-cell composition control also fails a72, which predates body-cell continuation.
Its candidate result does not by itself isolate the later keep-relaxation change. The fitting
kept control checks the ordinary case; the product tests separately exercise terminal keep
semantics, exact-height/header/editor exclusions and source identities. The benchmark evidence
claims only what these captured inputs and inspections establish.

`capture.json` binds exact source trees, build receipts, browser/font identities, input/PDF/
render-report/page-raster/screenshot hashes, reference eligibility and per-case checks.
`intermediate-ca99.json` and its manifest retain the original two-case record.
`intermediate-a42.json` and its supplemental inventories retain the later font-failure result.
`textbox-line-inventory.json` uses raw PDF word coordinates to compare inner-line advances
across host-spacing pairs; 0.75pt permits one CSS pixel of print rounding. Exact-inner cases
also check the authored 14pt advance. `bitmap-inventory.json` records Poppler bitmap entries
for the seven relevant image cases in both builds. These entries exclude masks; rounded PPI
is recorded without inferring precise physical dimensions or a fidelity score. Raw PDFs and
immutable reference bundles stay in ignored capture directories.

Validation completed for the frozen inputs: 374 Python tests, four Node adapter tests, and
manifest validation of all 496 cases passed. The rights/provenance audit passed for 2,031
source/artifact files, 496 regenerated DOCX inputs and 208 regenerated redline cases.

Reproduce from a separately provisioned renderer checkout and this repository:

```sh
git -C "$RENDERER_SOURCE" fetch https://github.com/JSv4/Docxodus.git review/export-reliability-cc575
git -C "$RENDERER_SOURCE" checkout --detach "$RENDERER_COMMIT"
python3 -m bench.fixtures
python3 -m bench validate
python3 -m bench build-docxodus --source "$RENDERER_SOURCE" --commit "$RENDERER_COMMIT"
```

Use the full source SHA from the result table, not a moving branch head. The public review
branch retains cc575, a42 and their ca99 ancestor. `focused-manifest.json` is the final 40-case contract.
Obtain the environment/font contract through `bench.environment.environment`, then use
`Capture.mjs SOURCE MANIFEST OUTPUT ENVIRONMENT_JSON`, `Inspect.py MANIFEST OUTPUT/capture.json`,
and `python3 -m bench reference libreoffice --manifest MANIFEST --out REFERENCE_DIR`.
`Compose.py MANIFEST REFERENCE_DIR BASELINE_DIR CANDIDATE_DIR [INTERMEDIATE_DIR]` adds labels
with optional Pillow. `InspectLines.py BASELINE_DIR CANDIDATE_DIR` and
`InspectPictures.py BASELINE_DIR CANDIDATE_DIR` reproduce the supplemental raw-PDF inventories.
The benchmark harness remains standard-library-only. Capture refuses dirty tracked renderer
sources and verifies every receipt-bound asset and input hash before export.

## Case sheets

Each sheet labels the exact renderer revisions and includes all pages.

### export-inline-context-paragraph-automatic

![export-inline-context-paragraph-automatic](export-inline-context-paragraph-automatic.png)

### export-inline-context-paragraph-automatic-note

![export-inline-context-paragraph-automatic-note](export-inline-context-paragraph-automatic-note.png)

### export-inline-context-paragraph-exact-control

![export-inline-context-paragraph-exact-control](export-inline-context-paragraph-exact-control.png)

### export-inline-context-empty-tab

![export-inline-context-empty-tab](export-inline-context-empty-tab.png)

### export-inline-context-empty-tab-control

![export-inline-context-empty-tab-control](export-inline-context-empty-tab-control.png)

### export-inline-context-table-bookmark

![export-inline-context-table-bookmark](export-inline-context-table-bookmark.png)

### export-inline-context-table-bookmark-control

![export-inline-context-table-bookmark-control](export-inline-context-table-bookmark-control.png)

### export-inline-context-merged-grid-tall

![export-inline-context-merged-grid-tall](export-inline-context-merged-grid-tall.png)

### export-inline-context-merged-grid-fitting-control

![export-inline-context-merged-grid-fitting-control](export-inline-context-merged-grid-fitting-control.png)

### export-inline-context-merged-grid-unmerged-control

![export-inline-context-merged-grid-unmerged-control](export-inline-context-merged-grid-unmerged-control.png)

### export-inline-context-style-frame-empty

![export-inline-context-style-frame-empty](export-inline-context-style-frame-empty.png)

### export-inline-context-style-frame-wrap-only

![export-inline-context-style-frame-wrap-only](export-inline-context-style-frame-wrap-only.png)

### export-inline-context-style-frame-ordinary-control

![export-inline-context-style-frame-ordinary-control](export-inline-context-style-frame-ordinary-control.png)

### export-inline-context-positioned-frame-control

![export-inline-context-positioned-frame-control](export-inline-context-positioned-frame-control.png)

### export-inline-context-wrap-clearance-encoded-anchor

![export-inline-context-wrap-clearance-encoded-anchor](export-inline-context-wrap-clearance-encoded-anchor.png)

### export-inline-context-wrap-clearance-encoded-wrap

![export-inline-context-wrap-clearance-encoded-wrap](export-inline-context-wrap-clearance-encoded-wrap.png)

### export-inline-context-wrap-clearance-signed-control

![export-inline-context-wrap-clearance-signed-control](export-inline-context-wrap-clearance-signed-control.png)

### export-inline-context-wrap-clearance-positive-control

![export-inline-context-wrap-clearance-positive-control](export-inline-context-wrap-clearance-positive-control.png)

### export-inline-context-header-image-undecodable

![export-inline-context-header-image-undecodable](export-inline-context-header-image-undecodable.png)

### export-inline-context-header-image-decodable-control

![export-inline-context-header-image-decodable-control](export-inline-context-header-image-decodable-control.png)

### export-inline-context-cell-oversized-kept

![export-inline-context-cell-oversized-kept](export-inline-context-cell-oversized-kept.png)

### export-inline-context-cell-fitting-kept-control

![export-inline-context-cell-fitting-kept-control](export-inline-context-cell-fitting-kept-control.png)

### export-inline-context-cell-oversized-unkept-control

![export-inline-context-cell-oversized-unkept-control](export-inline-context-cell-oversized-unkept-control.png)

### export-inline-context-float-square

![export-inline-context-float-square](export-inline-context-float-square.png)

### export-inline-context-float-square-control

![export-inline-context-float-square-control](export-inline-context-float-square-control.png)

### export-inline-context-float-tight

![export-inline-context-float-tight](export-inline-context-float-tight.png)

### export-inline-context-float-tight-control

![export-inline-context-float-tight-control](export-inline-context-float-tight-control.png)

### export-inline-context-tab-segment-long

![export-inline-context-tab-segment-long](export-inline-context-tab-segment-long.png)

### export-inline-context-tab-segment-fitting-control

![export-inline-context-tab-segment-fitting-control](export-inline-context-tab-segment-fitting-control.png)

### export-inline-context-tab-segment-ordinary-control

![export-inline-context-tab-segment-ordinary-control](export-inline-context-tab-segment-ordinary-control.png)

### export-inline-context-shape-atoms

![export-inline-context-shape-atoms](export-inline-context-shape-atoms.png)

### export-inline-context-shape-atoms-control

![export-inline-context-shape-atoms-control](export-inline-context-shape-atoms-control.png)

### export-inline-context-textbox-drawingml-natural-host1

![export-inline-context-textbox-drawingml-natural-host1](export-inline-context-textbox-drawingml-natural-host1.png)

### export-inline-context-textbox-drawingml-natural-host3

![export-inline-context-textbox-drawingml-natural-host3](export-inline-context-textbox-drawingml-natural-host3.png)

### export-inline-context-textbox-drawingml-exact-host1

![export-inline-context-textbox-drawingml-exact-host1](export-inline-context-textbox-drawingml-exact-host1.png)

### export-inline-context-textbox-drawingml-exact-host3

![export-inline-context-textbox-drawingml-exact-host3](export-inline-context-textbox-drawingml-exact-host3.png)

### export-inline-context-textbox-vml-natural-host1

![export-inline-context-textbox-vml-natural-host1](export-inline-context-textbox-vml-natural-host1.png)

### export-inline-context-textbox-vml-natural-host3

![export-inline-context-textbox-vml-natural-host3](export-inline-context-textbox-vml-natural-host3.png)

### export-inline-context-textbox-vml-exact-host1

![export-inline-context-textbox-vml-exact-host1](export-inline-context-textbox-vml-exact-host1.png)

### export-inline-context-textbox-vml-exact-host3

![export-inline-context-textbox-vml-exact-host3](export-inline-context-textbox-vml-exact-host3.png)
