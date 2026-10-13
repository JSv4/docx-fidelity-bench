# DOCX fidelity bench

An independent MIT benchmark of delivered PDF rendering. The harness and all 48 input documents are authored in this repository. It measures layout, visible content, physical pages, fonts, and declared feature assertions. It produces portable HTML evidence and JSON measurements.

The initial reference track is **LibreOffice**, pinned in CI to 25.8.7.3. Word Online, OneDrive, and desktop Word captures can be registered separately; **Word fidelity is not measured until those references exist**. The current suite is `core-v14`, with report-only renderer CI. Close-match thresholds have not been calibrated as release gates.

The [2026-10-11 results](RESULTS.md) measure remote Docxodus main `6e0e6ca` on the 12-case `core-v3` suite: 57.92/100, with 9/12 mandatory passes and 1/12 close matches. Repeated LibreOffice exports score 100/100. Full evidence is retained by the linked CI run. `core-v4` added an absolute textbox control and a zero-relative-dimension reproduction for [Docxodus #1076](https://github.com/JSv4/Docxodus/issues/1076). `core-v5` added an empty-header control and a hidden-only header reproduction for [Docxodus #1077](https://github.com/JSv4/Docxodus/issues/1077), each with a following visible header line to check paragraph flow. `core-v6` adds zero-width inline glyph and overindented word reproductions, an ordinary glyph control, and a drawing-only textbox host for [Docxodus #1078](https://github.com/JSv4/Docxodus/issues/1078). The existing absolute textbox supplies its visible-host control. `core-v7` adds twenty-row vertical-merge ledgers and unmerged controls for [Docxodus #1079](https://github.com/JSv4/Docxodus/issues/1079), covering an early merge and a merge crossing the preferred page boundary. `core-v8` adds ninety-line archive registers and paragraph controls for [Docxodus #1080](https://github.com/JSv4/Docxodus/issues/1080), covering explicit text-wrapping breaks and two empty lines near page boundaries. `core-v9` adds integral/half-point page width and height pairs for [Docxodus #1081](https://github.com/JSv4/Docxodus/issues/1081). These expose Chromium PDF size quantization; the benchmark retains its 0.25pt physical-geometry check and reports the fractional cases as geometry failures even when the export API accepts bounded print rounding. `core-v10` adds three-page legacy `w:pgNum` headers and equivalent complex decimal `PAGE` field controls for [Docxodus #1082](https://github.com/JSv4/Docxodus/issues/1082), including a Roman-numbered section restarted at twelve. Two additional simple `PAGE` field cases record a separate Docxodus gap: its converter keeps their cached value rather than substituting the current page; the complete number inventory and per-page placement assertions expose that failure. LibreOffice 25.8.7.3 drops the legacy blocks, so its legacy captures fail the declared number inventory and are not valid references; those two cases need a compliant reference capture. `core-v11` adds ninety-line footnote inventories and paragraph controls for [Docxodus #1083](https://github.com/JSv4/Docxodus/issues/1083), with ordinary hard breaks and two empty lines near note-band boundaries. Marker placement assertions and complete inventories retain continuation and layout differences as failures, including the existing inset and spacing applied to later footnote paragraphs. `core-v12` adds single/dashed paragraph-border cards with omitted, explicit zero, and explicit thin sizes for [Docxodus #1084](https://github.com/JSv4/Docxodus/issues/1084). The standard leaves the omitted-size default application-defined; these cases retain differences between renderer defaults and the existing thin-border mapping in raster measurements. `core-v13` adds six universal-unit indentation inventories, an equivalent twip control, and a smaller point/twip pair for [Docxodus #1085](https://github.com/JSv4/Docxodus/issues/1085). Physical/logical edges, first-line indents, and bordered hanging paragraphs are included. Existing direction marks added to RTL PDF text remain failures of the exact token/marker assertions, including in the numeric controls. The prior 48 DOCX inputs are byte-identical; new reference registration and a full `core-v13` score remain pending. `core-v14` adds eleven original page-margin inventories for [Docxodus #1086](https://github.com/JSv4/Docxodus/issues/1086): six equivalent universal-unit forms and a twip control, a two-page point/twip pair with repeated running stories, and a millimeter/rounded-twip pair. All six body/story margins are exercised. These packages validate against the official ECMA Transitional XSD; the SDK's integer-only page-margin validation rejects unit forms. All 57 preceding DOCX inputs remain byte-identical. Focused local LibreOffice checks pass all 89 mandatory assertions, with 2/11 close matches; existing raster and line-placement differences remain visible in the numeric controls. New reference registration and a full `core-v14` score remain pending. Historical `core-v3` scores cannot be compared directly with the expanded suite.

## What is included

| Category | Cases |
| --- | --- |
| Columns | Continuous section, balanced ending, explicit column break |
| Paragraphs | Authored agreement, heading at page start, heading kept with following paragraph; empty and hidden-only header paragraphs; zero-width inline glyphs and overindented letter wrapping |
| Notes | Footnote placement, lower-Roman endnote placement |
| Tables | Nested table, inherited cell margins; early and page-boundary vertical merges with unmerged controls |
| Images | Square and tight wrapping around an authored diamond; absolute and zero-relative textbox dimensions; drawing-only textbox hosts |

Each fixture has its own hash, generator identity, rights record, complete visible token inventory, and optional placement assertions in [the manifest](fixtures/manifest.json). Regenerating the corpus must produce identical bytes. See [authorship and rights](RIGHTS.md).

## Score

At 96 DPI, without alignment or resizing, a page scores `100 × min(SSIM, ink F1)`. Ink F1 uses one-pixel tolerance. A case takes its worst page score and becomes **zero** on a mandatory failure. The suite averages each category's mean equally. Missing references or broken measurement infrastructure make the run **incomplete**, with no suite headline score. Known candidate conversion failures stay in the suite with zero scores.

The score is layout similarity, not a percentage of document correctness. Report coverage, mandatory pass rate, and close-match rate alongside it. Read [the exact scoring contract](docs/SCORING.md), or [the Word document](docs/SCORING.docx).

## Run

Python 3.11 or newer is sufficient for the harness and tests; there are no Python package dependencies. Provision LibreOffice, Poppler (`pdftoppm`, `pdftotext`, `pdffonts`), qpdf 11 or newer, fontconfig, and Liberation Serif separately. To run Docxodus, also provision Node.js 22.13 or newer, .NET 10, its `wasm-tools` workload, and Chromium's sandbox host prerequisites.

```sh
python3 -m unittest discover -s tests -v
python3 -m bench validate
python3 -m bench reference libreoffice --out references/lo-v1
```

Build a separately checked-out, clean Docxodus source tree at an exact full commit. No renderer code or renderer fixtures are copied into this repository. The CI checkout selects production source paths and excludes fixture directories.

```sh
python3 -m bench build-docxodus --source /path/to/Docxodus --commit FULL_COMMIT_SHA
export DOCXODUS_SOURCE_ROOT=/path/to/Docxodus
export DOCXODUS_EXPORT_MODULE=/path/to/Docxodus/npm-export/dist/index.js
python3 -m bench run --reference references/lo-v1/bundle.json \
  --adapter docxodus --candidate FULL_COMMIT_SHA --out runs/example --gate report
```

Open `runs/example/index.html`. The adapter uses `@docxodus/export`'s public PDF API, requires the source-bound build record, verifies input and output digests, retains the production report, uses configured fonts, and keeps Chromium's process sandbox. It never silently uses an unrecorded distribution directory. On a host without the required sandbox, the result is unmeasured, not a claimed rendering failure.

`BENCH_LIBREOFFICE` can select an explicit LibreOffice executable. All tool versions and binary hashes, font hashes, reference PDF hashes, profiles, metric version, and suite identity are recorded. Retain `bundle.json` and its PDFs together; comparisons against a different reference bundle are rejected. Reference regeneration can change PDF metadata and therefore creates a new bundle identity.

For an identical-engine calibration run, use `--adapter libreoffice --candidate YOUR_REFERENCE_BUILD`. The reports must reach 100 with mandatory checks passing before treating the measurement setup as established.

## Gates and records

`--gate report` exits zero only for a complete measured run; known renderer failures remain visible with zero scores. `--gate mandatory` also requires all mandatory checks. `--gate close` additionally requires SSIM ≥ 0.98 and ink F1 ≥ 0.95 on every page. An incomplete run exits 2 in every mode.

```sh
python3 -m bench compare runs/before/result.json runs/after/result.json --tolerance 0
python3 -m bench record-propose runs/example/result.json --out proposed-record.json
```

Regression comparison refuses changed references, fonts, measurement tools, suites, metrics, adapters, or candidate runtime. Candidate source commits may differ. Tolerances are explicit, use each metric's units, and require repeat-run calibration; no nonzero tolerance is supplied by default. A record proposal requires a complete run and current input/generator hashes. It never replaces an existing record. Review the visual evidence before adopting a proposal; CI does not refresh records.

## Add a case or adapter

Author a focused DOCX with original text and graphics, add a generator and rights record, declare all visible token counts and versioned assertions, and add its ID and primary category to a versioned suite. The runner discovers manifest records; no scoring change is needed to add a case. The current check registry supports `marker-region`, `same-page`, and `marker-reference-position`; unknown types and versions are rejected. Region version 2 declares a 0.0001-point boundary tolerance for PDF coordinate serialization; version 1 retains exact boundaries. Reference-position checks compare a unique marker's page and top-left PDF position with its reference, within the declared tolerance in points. New check implementations need positive and negative examples. The corpus generator is intentionally transparent and deterministic.

Adding or changing cases requires a new suite version and a like-for-like rerun of the prior suite for historical comparisons. New references are explicitly pending until registered. No case is dropped because a renderer fails it.

Adapters receive one JSON request on stdin and return one JSON response on stdout. See [the protocol](docs/ADAPTERS.md). Renderer diagnostics can explain a mismatch but cannot override PDF measurements. All generated reports stay outside the source tree; CI uploads them as downloadable artifacts.

## Word capture later

Use an authenticated Word export route to convert the exact registered inputs, preserve the original PDFs, and record input/PDF digests, provider, method, reported build (explicitly `null` if unavailable), platform, capture date, final/hidden review profile, approved artifact rights, and the exact font contract. Supply each PDF as `CASE_ID.pdf` and register the operator-reviewed capture:

```sh
python3 -m bench reference import --metadata capture.json \
  --pdf-dir /path/to/captured-pdfs --out references/word-v1
```

The metadata format is documented in [Word capture](docs/WORD_CAPTURE.md). Tracks `word-online`, `word-onedrive`, and `word-desktop` remain distinct. A missing or ineligible capture blocks a complete Word suite score.
