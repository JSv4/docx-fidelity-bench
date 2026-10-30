# Export reliability: original reproducers and controls

Thirty-four independently authored PDF-track inputs cover export availability, source content,
and page-relative background placement. The generator imports no renderer fixture or helper.
`core-v74` contains 428 cases; all 394 previous DOCX inputs remain byte-identical. Their
manifest case records change only the required shared generator hash; profiles, tokens,
assertions, fonts, versions, rights, and input hashes are unchanged.

| Exact renderer source | PDFs delivered | Independent PDF checks passed |
|---|---:|---:|
| Baseline [`a72aac79858321ed64cdc850c2e66f4b4de59153`](https://github.com/JSv4/Docxodus/commit/a72aac79858321ed64cdc850c2e66f4b4de59153) | 18/34 | 16/34 |
| Intermediate [`6944c5e92d84662b0e46676576bae7169cb4b92c`](https://github.com/JSv4/Docxodus/commit/6944c5e92d84662b0e46676576bae7169cb4b92c) | 34/34 | 32/34 |
| Candidate [`73f2f8d5e0f63dd31e2d40017c90a4f4dd23215d`](https://github.com/JSv4/Docxodus/commit/73f2f8d5e0f63dd31e2d40017c90a4f4dd23215d) | 34/34 | 34/34 |

These are **unscored public-API diagnostics**. The strict benchmark adapter returned
`ENVIRONMENT_INELIGIBLE` because this host denies the user namespaces required by its pinned
Chromium sandbox. Captures use a borrowed system Chrome with its sandbox enabled, exact
source-bound WASM/JavaScript builds, strict fonts and an explicit hashed font directory.
No sandbox restriction was disabled. These captures are not registered candidate scores,
a full-suite result, or a claim of Word parity.

Independent PDF inspection checks the full visible token inventory, font contract, finite page
geometry, and any authored marker/page assertions. All 16 previously passing checks still pass;
16 failed baseline conversions now deliver complete PDFs. The two remaining intermediate failures
were page-background pictures displacing the body marker; both pass in the final candidate.
The screenshots below show all pages, including an explicit error panel when no baseline PDF
was delivered. Page rasters retain their original 96-DPI pixels.

LibreOffice produced 33 eligible references. The over-wide body-table reference remains
**ineligible** because it clips the rightmost visible token. Its screenshot is retained and
labeled; that reference is not permission to omit the token. The candidate retains all three
cell labels. Running-story spacing still differs visually from LibreOffice: the candidate
reserves the additive margins used by its final flex layout. The spacing fix establishes
content preservation, not matching vertical spacing. LibreOffice also partly clips the first
textbox label in both compact textbox cases despite passing text-extraction checks; those
rasters are not evidence of visual completeness. The candidate shows both labels fully.
LibreOffice uses the 200-by-100pt fallback for the relative-size background picture; the
candidate honors its authored 100-percent page size. This is another visible reference
difference, not a measured reference match.
Edge-cell source-derived marker regions
pass on both baseline controls and the candidate, and their baseline/candidate x positions are
unchanged. Near-page image sizing, standalone HTML reopening, off-paper page counts, and browser
shutdown timing are outside this focused set.

| Original mechanism and paired control | Product change |
|---|---|
| Oversized kept paragraph / unkept paragraph | [Docxodus #1430](https://github.com/JSv4/Docxodus/pull/1430) |
| Header and footer paragraph spacing / zero margins | [#1432](https://github.com/JSv4/Docxodus/pull/1432) |
| Long paragraph and nested table in body cells / ordinary body paragraphs | [#1433](https://github.com/JSv4/Docxodus/pull/1433) |
| Malformed unused XML / well-formed unused XML | [#1434](https://github.com/JSv4/Docxodus/pull/1434) |
| Oversized citing table / fitting citing table | [#1435](https://github.com/JSv4/Docxodus/pull/1435) |
| Fractional twip row height and tab / equivalent point measures | [#1436](https://github.com/JSv4/Docxodus/pull/1436) |
| Over-wide table / fitting grid | [#1437](https://github.com/JSv4/Docxodus/pull/1437) |
| Header/footer edge cells in margins / cells inside text width | [#1438](https://github.com/JSv4/Docxodus/pull/1438) |
| Rowless table, joined hidden mark, final hidden mark / visible carriers | [#1441](https://github.com/JSv4/Docxodus/pull/1441) |
| Wholly clipped blank textbox line / no trailing line | [#1442](https://github.com/JSv4/Docxodus/pull/1442) |
| Page-origin absolute and relative-size header pictures / inline picture | [#1444](https://github.com/JSv4/Docxodus/pull/1444) |

[#1431](https://github.com/JSv4/Docxodus/pull/1431) addresses an owned-browser process shutdown
deadline. A document alone cannot reproduce a suspended browser process; its process red/green
test remains in the product repository. Ordinary documents here provide rendering controls only.

`capture.json` binds input/PDF/page-raster/screenshot hashes, exact source trees and build identity
hashes, font/browser identities, reference eligibility, and per-case checks. `intermediate-6944.json`
retains the earlier result without relabeling it as the final candidate. No reference is imported
from the product repository. Raw PDFs and immutable reference bundles remain in ignored capture
directories; the committed PNGs and hash records are review evidence, not scoring inputs.

Validation passed: 374 Python contract tests, 4 Node adapter tests, manifest validation, and
provenance/byte-regeneration audit for all 428 DOCX and 208 redline cases. Author visual review
covered every new case; a separate adversarial review checked the generator, capture pipeline,
manifest changes, and qualifications. No unresolved content or scoring issue was found.

Reproduce from a separately provisioned renderer checkout and this repository:

```sh
git -C "$RENDERER_SOURCE" fetch https://github.com/JSv4/Docxodus.git review/export-reliability-73f2
git -C "$RENDERER_SOURCE" checkout --detach "$RENDERER_COMMIT"
python3 -m bench.fixtures
python3 -m bench validate
python3 -m bench build-docxodus --source "$RENDERER_SOURCE" --commit "$RENDERER_COMMIT"
```

The public review branch retains both intermediate and candidate commits listed above.

`focused-manifest.json` preserves the exact captured cases and distinct diagnostic suite identity.
Obtain the font contract
and font directories with `bench.environment.environment`. Then use `Capture.mjs SOURCE MANIFEST
OUTPUT ENVIRONMENT_JSON`, `Inspect.py MANIFEST OUTPUT/capture.json`, and
`python3 -m bench reference libreoffice --manifest MANIFEST --out REFERENCE_DIR`.
`Compose.py MANIFEST REFERENCE_DIR BASELINE_DIR CANDIDATE_DIR` adds renderer labels with optional
Pillow; the benchmark harness itself retains its standard-library-only dependency policy.
The capture script verifies source/build/input hashes and refuses dirty tracked renderer sources.

## export-reliability-header-spacing

![export-reliability-header-spacing](export-reliability-header-spacing.png)

## export-reliability-header-spacing-control

![export-reliability-header-spacing-control](export-reliability-header-spacing-control.png)

## export-reliability-footer-spacing

![export-reliability-footer-spacing](export-reliability-footer-spacing.png)

## export-reliability-footer-spacing-control

![export-reliability-footer-spacing-control](export-reliability-footer-spacing-control.png)

## export-reliability-header-margin-cells

![export-reliability-header-margin-cells](export-reliability-header-margin-cells.png)

## export-reliability-header-margin-cells-control

![export-reliability-header-margin-cells-control](export-reliability-header-margin-cells-control.png)

## export-reliability-footer-margin-cells

![export-reliability-footer-margin-cells](export-reliability-footer-margin-cells.png)

## export-reliability-footer-margin-cells-control

![export-reliability-footer-margin-cells-control](export-reliability-footer-margin-cells-control.png)

## export-reliability-rowless-table

![export-reliability-rowless-table](export-reliability-rowless-table.png)

## export-reliability-hidden-joined-source

![export-reliability-hidden-joined-source](export-reliability-hidden-joined-source.png)

## export-reliability-hidden-final-mark

![export-reliability-hidden-final-mark](export-reliability-hidden-final-mark.png)

## export-reliability-rowless-table-control

![export-reliability-rowless-table-control](export-reliability-rowless-table-control.png)

## export-reliability-hidden-joined-source-control

![export-reliability-hidden-joined-source-control](export-reliability-hidden-joined-source-control.png)

## export-reliability-hidden-final-mark-control

![export-reliability-hidden-final-mark-control](export-reliability-hidden-final-mark-control.png)

## export-reliability-textbox-blank-tail

![export-reliability-textbox-blank-tail](export-reliability-textbox-blank-tail.png)

## export-reliability-textbox-blank-tail-control

![export-reliability-textbox-blank-tail-control](export-reliability-textbox-blank-tail-control.png)

## export-reliability-oversized-kept-paragraph

![export-reliability-oversized-kept-paragraph](export-reliability-oversized-kept-paragraph.png)

## export-reliability-oversized-kept-paragraph-control

![export-reliability-oversized-kept-paragraph-control](export-reliability-oversized-kept-paragraph-control.png)

## export-reliability-body-cell-paragraph

![export-reliability-body-cell-paragraph](export-reliability-body-cell-paragraph.png)

## export-reliability-body-cell-nested

![export-reliability-body-cell-nested](export-reliability-body-cell-nested.png)

## export-reliability-body-cell-control

![export-reliability-body-cell-control](export-reliability-body-cell-control.png)

## export-reliability-oversized-citing-table

![export-reliability-oversized-citing-table](export-reliability-oversized-citing-table.png)

## export-reliability-oversized-citing-table-control

![export-reliability-oversized-citing-table-control](export-reliability-oversized-citing-table-control.png)

## export-reliability-unused-xml

![export-reliability-unused-xml](export-reliability-unused-xml.png)

## export-reliability-unused-xml-control

![export-reliability-unused-xml-control](export-reliability-unused-xml-control.png)

## export-reliability-body-table-width

![export-reliability-body-table-width](export-reliability-body-table-width.png)

## export-reliability-body-table-width-control

![export-reliability-body-table-width-control](export-reliability-body-table-width-control.png)

## export-reliability-header-picture-page-absolute

![export-reliability-header-picture-page-absolute](export-reliability-header-picture-page-absolute.png)

## export-reliability-header-picture-page-relative

![export-reliability-header-picture-page-relative](export-reliability-header-picture-page-relative.png)

## export-reliability-header-picture-inline-control

![export-reliability-header-picture-inline-control](export-reliability-header-picture-inline-control.png)

## export-reliability-fractional-row

![export-reliability-fractional-row](export-reliability-fractional-row.png)

## export-reliability-fractional-tab

![export-reliability-fractional-tab](export-reliability-fractional-tab.png)

## export-reliability-fractional-row-control

![export-reliability-fractional-row-control](export-reliability-fractional-row-control.png)

## export-reliability-fractional-tab-control

![export-reliability-fractional-tab-control](export-reliability-fractional-tab-control.png)
