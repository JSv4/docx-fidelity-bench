# Export reliability: continuation and geometry controls

Twenty-eight independently authored Cobalt inputs extend the PDF track to `core-v75` (456
cases). One unchanged DrawingML background case joins them in this 29-case focused capture.
All 428 previous DOCX inputs remain byte-identical; previous case records change only the
required shared generator hash. The generator imports no product fixture or helper.

| Exact renderer source | PDFs delivered | Independent PDF checks passed |
|---|---:|---:|
| Baseline [`a72aac79858321ed64cdc850c2e66f4b4de59153`](https://github.com/JSv4/Docxodus/commit/a72aac79858321ed64cdc850c2e66f4b4de59153) | 16/29 | 14/29 |
| Candidate [`88d060e6ac35d9de87bfe7f64e13216316f115e5`](https://github.com/JSv4/Docxodus/commit/88d060e6ac35d9de87bfe7f64e13216316f115e5) | 29/29 | 29/29 |

These are **unscored public-API diagnostics**. The strict benchmark adapter reports
`ENVIRONMENT_INELIGIBLE` on this host because its pinned Chromium sandbox requires unavailable
user namespaces. A separately provisioned system Chrome, with its sandbox enabled, captured
exact source-bound WASM/JavaScript builds using strict fonts and a hashed font directory.
No sandbox restriction was disabled. There is no registered candidate score, full-suite score,
or claim of Word parity.

Independent PDF checks inspect the full authored visible-token inventory, font contract,
finite page geometry, and authored marker/page assertions. They do **not** compare the
candidate's page count, positions, or pixels with LibreOffice. All 14 baseline checks still
pass; 13 failed conversions now deliver checked PDFs. Both baseline page-background cases
delivered a PDF but displaced the body marker; both candidate marker checks pass.

The screenshots show every page at its original 96-DPI size, with errors displayed when no
baseline PDF was delivered. Author review covered every focused case. Candidate text and
picture content is visible, including all checkerboard edges in the image cases. Fitting image
controls retain their visual dimensions. `bitmap-inventory.json` independently records
Poppler bitmap entries for nine picture cases in each renderer (18 records, including explicit
baseline failures). All delivered PDFs have the expected counts. These entries exclude masks;
Poppler's integer PPI values are preserved as reported and do not establish precise physical
sizes or a fidelity score.

LibreOffice produced 25 eligible references. Four references remain **ineligible** for missing
authored visible tokens: the wide header table, wide footer table, contextual-spacing textbox,
and oversized inline picture. Their screenshots remain labeled. Candidate exports preserve
the complete token inventory; a reference omission does not make an omission acceptable.

Visual differences limit the interpretation of passing checks. LibreOffice places the outer
body label over textbox text in the contextual-spacing cases, including controls whose text
extraction passes. It reserves vertical space for the zero-font blank line, whereas the
candidate has no line height there. It keeps the framed cell paragraph in ordinary flow,
whereas the candidate honors its page position. Dashed border patterns differ. The floating
picture reproducer has **two candidate pages and one LibreOffice page**: the candidate moves
the complete picture and caption to page two. Its shorter-image control stays on one page in
both Docxodus builds. None of these differences is reported as a reference geometry match.

| Original mechanism and controls | Product change |
|---|---|
| Fractional single/dashed borders after standalone HTML reopening / integral border and spacing | [Docxodus #1439](https://github.com/JSv4/Docxodus/pull/1439) |
| Hard-break inline pictures / separate picture paragraphs | [#1440](https://github.com/JSv4/Docxodus/pull/1440) |
| Off-paper vector drawing / visible and edge-intersecting drawings | [#1443](https://github.com/JSv4/Docxodus/pull/1443) |
| Oversized inline picture / fitting single and fitting-pair pictures | [#1446](https://github.com/JSv4/Docxodus/pull/1446) |
| VML page background / unchanged DrawingML page-background control | [#1447](https://github.com/JSv4/Docxodus/pull/1447), [#1444](https://github.com/JSv4/Docxodus/pull/1444) |
| Floating picture taller than remaining body / shorter picture | [#1448](https://github.com/JSv4/Docxodus/pull/1448) |
| Zero-font blank paragraph / visible run and positive-height painted border | [#1449](https://github.com/JSv4/Docxodus/pull/1449) |
| Cell text promoted into a frame / ordinary cell text | [#1452](https://github.com/JSv4/Docxodus/pull/1452) |
| Same resolved style contextual spacing / ordinary and different-style spacing | [#1453](https://github.com/JSv4/Docxodus/pull/1453) |
| Blank fixed textbox below paper / visible on-paper textbox | [#1454](https://github.com/JSv4/Docxodus/pull/1454) |
| Over-wide header/footer tables / fitting grids | [#1464](https://github.com/JSv4/Docxodus/pull/1464) ([captured source](https://github.com/JSv4/Docxodus/commit/eba93b2eb37c2e35f82d8e551c6b38bc512ab444)) |

The border inputs trigger the product's own standalone-HTML reopen verification inside public
PDF export. The screenshots themselves are delivered PDFs, not separate browser screenshots
of saved HTML. Visible-content rejection controls for deliberately clipped text and off-paper
visible text remain in the product tests; the blank-box benchmark pair does not replace them.

`capture.json` binds input, PDF, page-raster and screenshot hashes to the exact source trees,
build identity hashes, font/browser identities, reference eligibility and per-case checks.
`bitmap-inventory.json` separately binds its source/PDF hashes and Poppler executable. Raw
PDFs and immutable reference bundles stay in ignored capture directories. These PNGs and hash
records are review evidence, not scoring inputs.

Validation: 374 Python contract tests, 4 Node adapter tests, manifest validation and the
provenance/byte-regeneration audit. Existing 428 case objects were compared field-by-field
apart from their shared generator hash. The 456 PDF-track packages and 208 redline cases
remain independently reproducible.

Reproduce from a separately provisioned renderer checkout and this repository:

```sh
git -C "$RENDERER_SOURCE" fetch https://github.com/JSv4/Docxodus.git review/export-reliability-next
git -C "$RENDERER_SOURCE" checkout --detach "$RENDERER_COMMIT"
python3 -m bench.fixtures
python3 -m bench validate
python3 -m bench build-docxodus --source "$RENDERER_SOURCE" --commit "$RENDERER_COMMIT"
```

The public review branch retains the exact candidate commit above. Use its full SHA or the
full baseline SHA for `RENDERER_COMMIT`; do not substitute a moving branch head.
`focused-manifest.json` preserves the captured cases and distinct diagnostic suite identity.
Obtain the environment/font contract with `bench.environment.environment`, then run
`Capture.mjs SOURCE MANIFEST OUTPUT ENVIRONMENT_JSON`, `Inspect.py MANIFEST OUTPUT/capture.json`,
and `python3 -m bench reference libreoffice --manifest MANIFEST --out REFERENCE_DIR`.
`Compose.py MANIFEST REFERENCE_DIR BASELINE_DIR CANDIDATE_DIR` adds labels around unchanged
rasters using optional Pillow. `InspectPictures.py BASELINE_DIR CANDIDATE_DIR` records the
bitmap inventory using Poppler. The benchmark harness remains standard-library-only.
Capture refuses dirty tracked renderer sources and validates source/build/input hashes.

## export-reliability-header-picture-page-absolute

![export-reliability-header-picture-page-absolute](export-reliability-header-picture-page-absolute.png)

## export-reliability-header-wide-table

![export-reliability-header-wide-table](export-reliability-header-wide-table.png)

## export-reliability-header-wide-table-control

![export-reliability-header-wide-table-control](export-reliability-header-wide-table-control.png)

## export-reliability-footer-wide-table

![export-reliability-footer-wide-table](export-reliability-footer-wide-table.png)

## export-reliability-footer-wide-table-control

![export-reliability-footer-wide-table-control](export-reliability-footer-wide-table-control.png)

## export-reliability-textbox-contextual-same-style

![export-reliability-textbox-contextual-same-style](export-reliability-textbox-contextual-same-style.png)

## export-reliability-textbox-contextual-ordinary-control

![export-reliability-textbox-contextual-ordinary-control](export-reliability-textbox-contextual-ordinary-control.png)

## export-reliability-textbox-contextual-different-style-control

![export-reliability-textbox-contextual-different-style-control](export-reliability-textbox-contextual-different-style-control.png)

## export-reliability-zero-font-blank

![export-reliability-zero-font-blank](export-reliability-zero-font-blank.png)

## export-reliability-zero-font-visible-control

![export-reliability-zero-font-visible-control](export-reliability-zero-font-visible-control.png)

## export-reliability-zero-font-border-control

![export-reliability-zero-font-border-control](export-reliability-zero-font-border-control.png)

## export-reliability-frame-cell

![export-reliability-frame-cell](export-reliability-frame-cell.png)

## export-reliability-frame-cell-control

![export-reliability-frame-cell-control](export-reliability-frame-cell-control.png)

## export-reliability-border-reopen-single

![export-reliability-border-reopen-single](export-reliability-border-reopen-single.png)

## export-reliability-border-reopen-dashed

![export-reliability-border-reopen-dashed](export-reliability-border-reopen-dashed.png)

## export-reliability-border-reopen-integral-control

![export-reliability-border-reopen-integral-control](export-reliability-border-reopen-integral-control.png)

## export-reliability-inline-picture-lines

![export-reliability-inline-picture-lines](export-reliability-inline-picture-lines.png)

## export-reliability-inline-picture-lines-control

![export-reliability-inline-picture-lines-control](export-reliability-inline-picture-lines-control.png)

## export-reliability-inline-picture-oversized

![export-reliability-inline-picture-oversized](export-reliability-inline-picture-oversized.png)

## export-reliability-inline-picture-fitting-control

![export-reliability-inline-picture-fitting-control](export-reliability-inline-picture-fitting-control.png)

## export-reliability-inline-picture-fitting-pair

![export-reliability-inline-picture-fitting-pair](export-reliability-inline-picture-fitting-pair.png)

## export-reliability-off-paper-blank-box

![export-reliability-off-paper-blank-box](export-reliability-off-paper-blank-box.png)

## export-reliability-off-paper-blank-box-control

![export-reliability-off-paper-blank-box-control](export-reliability-off-paper-blank-box-control.png)

## export-reliability-drawing-off-paper

![export-reliability-drawing-off-paper](export-reliability-drawing-off-paper.png)

## export-reliability-drawing-visible-control

![export-reliability-drawing-visible-control](export-reliability-drawing-visible-control.png)

## export-reliability-drawing-edge-control

![export-reliability-drawing-edge-control](export-reliability-drawing-edge-control.png)

## export-reliability-floating-picture-height

![export-reliability-floating-picture-height](export-reliability-floating-picture-height.png)

## export-reliability-floating-picture-height-control

![export-reliability-floating-picture-height-control](export-reliability-floating-picture-height-control.png)

## export-reliability-header-vml-background

![export-reliability-header-vml-background](export-reliability-header-vml-background.png)
