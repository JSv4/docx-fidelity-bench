# DOCX fidelity bench

An independent MIT benchmark of delivered PDF rendering and of document comparison. The harness and every input document are authored in this repository. It measures layout, visible content, physical pages, fonts, and declared feature assertions. It produces portable HTML evidence and JSON measurements.

The initial reference track is **LibreOffice**, pinned in CI to 25.8.7.3. Word reference PDFs can be registered as separate tracks. The current PDF suite is `core-v49`, with report-only renderer CI. A separate comparison track, `redline-v7`, scores redlines on accept/reject round trips; see [Redline track](#redline-track). Close-match thresholds have not been calibrated as release gates.

`core-v49` adds an original fitting nested footnote table and a matching ordinary-table control for Docxodus #1217. The nested cell ends with an unformatted structural paragraph; both cases require complete PDF text and keep all three note rows with their citation. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v7`.

`core-v47` and `redline-v6` add eight original bookmark-reviewer cases for Docxodus #1212: same-paragraph edits in body paragraphs, content controls and table cells, their outside-edit controls, and independent removal/movement decisions. Each case has final/original PDF views and an authored redline with per-reviewer projections. All earlier DOCX bytes remain unchanged.

`core-v36` adds six PDF views for Docxodus #1190: table-boundary comparison, row-boundary consolidation,
and a plain-paragraph text control, each in final and original views. Candidates perform the operation
on the authored source inputs before production PDF export; references use independently authored
expected documents. All 150 prior PDF inputs are unchanged. Bookmarks have no visible ink, so these
PDF cases check retained text and layout. Six companion redline cases verify exact marker boundaries,
accept/reject behavior and individual reviewer attribution; the semantic reader now visits markers
between rows and cells. Copying either input or moving a boundary cannot satisfy the checks.


`core-v37` adds ten final/original PDF views and five independent comment cases for #1195/#1196, with wrapper and reviewer controls. All prior inputs remain unchanged.

The [2026-10-14 core-v17 Docxodus results](docs/results/core-v17-docxodus.md) record main `a56b448` at 70.377 and the integrated fixes for Docxodus #1115, #1116 and #1119–#1126 at 97.774, with calibration 100 and every mandatory check passing. The [2026-10-11 results](RESULTS.md) measure remote Docxodus main `6e0e6ca` on the 12-case `core-v3` suite: 57.92/100, with 9/12 mandatory passes and 1/12 close matches. Repeated LibreOffice exports score 100/100. Full evidence is retained by the linked CI run. `core-v4` added an absolute textbox control and a zero-relative-dimension reproduction for [Docxodus #1076](https://github.com/JSv4/Docxodus/issues/1076). `core-v5` added an empty-header control and a hidden-only header reproduction for [Docxodus #1077](https://github.com/JSv4/Docxodus/issues/1077), each with a following visible header line to check paragraph flow. `core-v6` adds zero-width inline glyph and overindented word reproductions, an ordinary glyph control, and a drawing-only textbox host for [Docxodus #1078](https://github.com/JSv4/Docxodus/issues/1078). The existing absolute textbox supplies its visible-host control. `core-v7` adds twenty-row vertical-merge ledgers and unmerged controls for [Docxodus #1079](https://github.com/JSv4/Docxodus/issues/1079), covering an early merge and a merge crossing the preferred page boundary. `core-v8` adds ninety-line archive registers and paragraph controls for [Docxodus #1080](https://github.com/JSv4/Docxodus/issues/1080), covering explicit text-wrapping breaks and two empty lines near page boundaries. `core-v9` adds integral/half-point page width and height pairs for [Docxodus #1081](https://github.com/JSv4/Docxodus/issues/1081). These expose Chromium PDF size quantization; the benchmark retains its 0.25pt physical-geometry check and reports the fractional cases as geometry failures even when the export API accepts bounded print rounding. `core-v10` adds three-page legacy `w:pgNum` headers and equivalent complex decimal `PAGE` field controls for [Docxodus #1082](https://github.com/JSv4/Docxodus/issues/1082), including a Roman-numbered section restarted at twelve. Two additional simple `PAGE` field cases record a separate Docxodus gap: its converter keeps their cached value rather than substituting the current page; the complete number inventory and per-page placement assertions expose that failure. LibreOffice 25.8.7.3 drops the legacy blocks, so its legacy captures fail the declared number inventory and are not valid references; those two cases need a compliant reference capture. `core-v11` adds ninety-line footnote inventories and paragraph controls for [Docxodus #1083](https://github.com/JSv4/Docxodus/issues/1083), with ordinary hard breaks and two empty lines near note-band boundaries. Marker placement assertions and complete inventories retain continuation and layout differences as failures, including the existing inset and spacing applied to later footnote paragraphs. `core-v12` adds single/dashed paragraph-border cards with omitted, explicit zero, and explicit thin sizes for [Docxodus #1084](https://github.com/JSv4/Docxodus/issues/1084). The standard leaves the omitted-size default application-defined; these cases retain differences between renderer defaults and the existing thin-border mapping in raster measurements. `core-v13` adds six universal-unit indentation inventories, an equivalent twip control, and a smaller point/twip pair for [Docxodus #1085](https://github.com/JSv4/Docxodus/issues/1085). Physical/logical edges, first-line indents, and bordered hanging paragraphs are included. Existing direction marks added to RTL PDF text remain failures of the exact token/marker assertions, including in the numeric controls. The prior 48 DOCX inputs are byte-identical; new reference registration and a full `core-v13` score remain pending. `core-v14` adds eleven original page-margin inventories for [Docxodus #1086](https://github.com/JSv4/Docxodus/issues/1086): six equivalent universal-unit forms and a twip control, a two-page point/twip pair with repeated running stories, and a millimeter/rounded-twip pair. All six body/story margins are exercised. These packages validate against the official ECMA Transitional XSD; the SDK's integer-only page-margin validation rejects unit forms. All 57 preceding DOCX inputs remain byte-identical. Focused local LibreOffice checks pass all 89 mandatory assertions, with 2/11 close matches; existing raster and line-placement differences remain visible in the numeric controls. New reference registration and a full `core-v14` score remain pending. `core-v17` adds `tables-vmerge-boundary-merged-kept`, an authored keep-with-next control for the boundary merge whose direct LibreOffice capture splits the declared group (bench #17). References are now eligible only when they pass their case's own declared assertions. Unit-valued minimum row heights, which LibreOffice collapses, use proven whole-twip controls; the 25.075pt case uses a bounded nearest-twip control (bench #16). The nine indentation inventories, whose logical paragraph has contradictory legacy aliases, use two authored logical-only controls; Word adjudication remains pending (bench #18). It also adds four regression inventories: simple `PAGE`/`NUMPAGES` header fields, border spacing on indented, grouped and hanging paragraphs, a half-point page with ink near every edge, and an overflowing exact-height row. `core-v18` adds nineteen regression inventories: A4 pages with 1417-twip margins whose twelve exact lines fall one twip short of the body band or overfill it by one twip, against 1416/1418-twip controls (Docxodus #1164); exact-height rows that hide a whole paragraph, a borderless zero-height row and a table of only such rows (#1168); a repeated header row with exact and atLeast rules, and a bordered paragraph clipped by an exact row, whose border clipping only the raster score measures (#1171); and footnote layout around a note that fills nearly a whole page, a continued note that must stay last on its page (with a control), a carried note with deferred citations, a keep-with-next heading beside a running continuation, and a table row citing a keep-lines note too tall for its page (#1178, #1179, #1180 and #1182). `core-v19` makes the footnote cases independent of how wide a renderer draws the superscript note number, which differs between providers: their position checks now use a note's second line or a body line. Four note inputs change (the #1179 pair, the #1180 case, rebuilt with a thirty-line note cited on line 31 of page 1, and the carried-note case), and `notes-keep-lines-note-in-table` changes only its position marker; the other 107 inputs are byte-identical to `core-v18`. `core-v20` changes no input. It replaces the reference-relative positions of `notes-carried-note-defers-citations` and `notes-keep-lines-note-in-table` with Word-adjudicated assertions taken from Word reference PDFs of the exact inputs: the citing paragraphs after a carried note start, with their notes, on the page where it ends, leaving the page between to the continuation, and a table row citing a kept note too tall for the rest of its page moves to the note's page. LibreOffice 25.8.7.3 does neither. Its captures stay eligible because these assertions do not bind a LibreOffice capture (see the scoring contract), but a candidate that follows Word on these two cases is compared with LibreOffice pages that hold different lines, so its raster score there is capped below a close match. Word reference PDFs of the nineteen `core-v18` cases, captured from their `core-v19` inputs, were registered on the `word` track; Word substituted Times New Roman for the declared Liberation Serif, so every capture fails `declared-font-families` and is ineligible, and no Word-track score exists yet. The 92 inputs before `core-v18` remain byte-identical, and every new LibreOffice 25.8.7.3 capture passes every declared assertion that binds it. Historical `core-v3` scores cannot be compared directly with the expanded suite.

`core-v21` adds eight original decoration inventories for [Docxodus #1220](https://github.com/JSv4/Docxodus/issues/1220): double underline, double strike, combined underline and strike, and dotted blue underline, each paired with a simpler control. Their raster scores measure line count, pattern and color; text inventories alone cannot detect these defects. All 111 preceding DOCX inputs remain byte-identical. Reference registration and full suite scoring are pending.

`core-v22` adds a zero-indent changed paragraph and an indented control for [Docxodus #1221](https://github.com/JSv4/Docxodus/issues/1221). Both request markup with Word-style revision presentation; the adapter now forwards this optional profile setting. The raster score measures bar placement; text inventories retain the inserted text. All 119 prior DOCX input hashes are unchanged. Reference registration and scoring are pending.

`core-v23` adds a bold-only revision with inherited font/size and an explicit matching snapshot control for [Docxodus #1222](https://github.com/JSv4/Docxodus/issues/1222). All 121 prior DOCX hashes remain unchanged. These cases also check the `title` attached to the unique `FormatLabel` marker in delivered standalone HTML: the PDF alone cannot expose an incorrect tooltip. HTML feature coverage is reported separately from the unchanged PDF score and participates in regression checks. A renderer without the requested HTML artifact has unmeasured HTML coverage. Reference-engine calibration remains PDF-only. New references and full suite scoring are pending.

`core-v24` adds an original numbered heading with a hidden paragraph mark and an explicitly visible-mark control for [Docxodus #1223](https://github.com/JSv4/Docxodus/issues/1223). The number inventory and heading/body placement checks retain visibility and line-flow failures. Local reference-engine observations place the hidden-mark body on the heading line and the control body on the following line; these are diagnostic observations, not registered reference scores. All 123 earlier DOCX hashes remain unchanged. New reference registration and full suite scoring remain pending.

`core-v25` adds three manual labels with hanging indentation and left-title/right-page-number tab stops, plus a narrow-label single-left-tab control for [Docxodus #1224](https://github.com/JSv4/Docxodus/issues/1224). Exact 12pt line spacing isolates tab geometry from automatic line-height differences. Complete number inventories and six title/page-number position assertions retain skipped stops, misplaced leaders and incorrect page-number alignment. Explicit spaces around the tab leader keep page-number words separate in PDF extraction. The source-verified `isolated-dot-leaders-v1` policy excludes only isolated decorative dot words from token counts; raw word geometry and all raster ink remain measured. All 125 earlier input hashes remain unchanged; reference registration and full suite scoring remain pending.

`core-v26` adds an original page-anchored footer paragraph frame and an otherwise identical ordinary-flow control for [Docxodus #1225](https://github.com/JSv4/Docxodus/issues/1225). The frame declares a 42pt horizontal offset, a 1pt text-relative vertical offset and a 504pt width; a centered ordinary footer paragraph follows it. Exact 12pt line spacing isolates placement. Body, frame-text and centered-footer position assertions retain misplacement while full token inventories retain missing or duplicated text. All 127 earlier input hashes remain unchanged; reference registration and full-suite scoring remain pending.


`core-v27` adds original 240-token and eight-token margin comments for [Docxodus #1226](https://github.com/JSv4/Docxodus/issues/1226). The PDF profile hides comments and retains complete body text and physical page checks. An explicit margin-comment HTML profile checks the intact authored note paragraph and whether its unique final token can be reached through user-scrollable viewports. The observer opens the actual delivered HTML in a separate offline, script-disabled browser context; hidden clipping cannot pass as scrolling. HTML coverage remains separate from PDF scores. All 129 earlier input hashes remain unchanged; reference registration and full-suite scoring remain pending.

`core-v28` adds an original three-level comment thread and a flat-note control, plus long-author and short-author header cases for [Docxodus #1227](https://github.com/JSv4/Docxodus/issues/1227). The nesting pair has identical comment bodies, authors and dates and differs only in parent links; the header pair differs only in author length. Their PDFs hide comments and retain body/page checks. The margin-profile HTML companion checks that every note marker renders at the declared 13.6px text size, using computed styles from all of its visible inline fragments and actual clipping geometry. The separate one-inch-margin header pair requires the unique author marker to retain its 12.24px header text size and remain fully contained in the column. Header dates, badges and links are also covered by the native browser regressions. All 131 earlier DOCX input hashes remain unchanged. New reference registration and full-suite scoring remain pending.

`core-v29` adds original modern-UTC and legacy-only timestamp cases, plus a margin-year case and an authored-year control for [Docxodus #1228](https://github.com/JSv4/Docxodus/issues/1228). The inline HTML companion checks the exact timestamp through the authored durable-ID graph. The margin-year case requires the generated visible year and its matching timestamp; the margin control checks that an authored year token remains readable. Endnote caption formatting is covered by the native regressions. PDF comments remain hidden, with ordinary body/page checks. All 135 earlier DOCX inputs are unchanged. These HTML checks complement the PDF evidence; they do not claim that hidden comments can be measured in the PDF. New reference registration and full-suite scoring remain pending.

`core-v30` adds an original paginated comment return link and an ordinary body-bookmark link control for [Docxodus #1229](https://github.com/JSv4/Docxodus/issues/1229). Their body content and PDF profile are the same; the reproduction carries a comment and checks both the delivered return `href` and its body's `[4]` target ID. The control checks its authored body-bookmark `href`. PDF evidence covers body text, fonts and physical pages; return navigation is measured in delivered HTML. Native browser tests additionally cover keyboard navigation, later pages, floating body frames, hidden/clipped/transparent and ambiguous targets. All 139 earlier DOCX hashes remain unchanged. New reference registration and full-suite scoring remain pending.

`core-v31` adds an original CSS child-selector repro and a descendant-selector control for
[Docxodus #1230](https://github.com/JSv4/Docxodus/issues/1230), bringing the suite to 143 cases.
The two DOCX packages are byte-identical. Their PDF profiles use no CSS override; their separate
HTML profiles apply equivalent 32px styles to a short margin-note marker. Unlike body text
frozen with print-precision scaling, the note retains its requested CSS size. The existing
computed-style observer requires every visible marker fragment to have that size. `additionalCss` is permitted only in HTML profiles,
forwarded only for HTML export, and bound to the HTML artifact contract. Reference PDF renderers
need no custom-CSS support. All 141 preceding DOCX hashes remain unchanged.

Older Node exports that reject `additionalCss` are unmeasured for these HTML checks. A controlled
before/after comparison may use an API-enabled baseline with only the core CSS serializer patch
reverted; this distinction must be recorded. The original native conversion API independently
reproduces the defect on unmodified main. New references and full-suite scoring remain pending.

`core-v34` adds `paragraph-contract-times-new-roman` for [bench #33](https://github.com/JSv4/docx-fidelity-bench/issues/33), bringing the suite to 150 cases. It differs from the original justified agreement only in its requested font family. Word Online substitutes Times New Roman when the original requests Liberation Serif; the explicit variant allows a comparison with the declared family. All 149 preceding DOCX hashes remain unchanged. Both cases retain their full token inventories and raster measurements; neither declares marker-position assertions. Times New Roman is separately provisioned for rendering. Word is used only to capture reference PDFs, and is not a harness or test dependency. The [Word capture and focused comparison](docs/results/paragraph-contract-word.md) retain font-version differences and the original ineligible capture. New full-suite reference registration and scoring remain pending.

`core-v41` adds eight final/original PDF views and four independent complex-field consolidation cases for #1206. The redline track checks field characters, cached results, bookmarks and reviewer attribution. PDF references recalculate body PAGE fields; Docxodus intentionally preserves their cached body text, so the two final views with an edited cache report a visible-token mismatch (7 versus 1). This difference remains measured, with no token exclusion or relaxed assertion. The other six views compare retained text and layout directly.

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

Python 3.11 or newer is sufficient for the harness and tests; there are no Python package dependencies. Provision LibreOffice, Poppler (`pdftoppm`, `pdftotext`, `pdffonts`), qpdf 11 or newer, fontconfig, Liberation Serif, and Times New Roman separately. Times New Roman is required by the agreement variant; on Ubuntu the rendering workflow provisions it through `ttf-mscorefonts-installer` under the font package's own license (see [RIGHTS.md](RIGHTS.md)). Docxodus requires font directories without symlinks: CI removes the installer's filename aliases, while local runs can use regular-file copies of the declared fonts and point fontconfig at that directory. Font hashes must still match the reference contract. To run Docxodus, also provision Node.js 22.13 or newer, .NET 10, its `wasm-tools` workload, and Chromium's sandbox host prerequisites.

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

Open `runs/example/index.html`. In CI, the `reference_run` input reuses an earlier run's immutable reference bundle and its 100-point calibration instead of registering new captures, then runs `bench compare --tolerance 0` against that run's candidate result as report-only evidence. Fresh registrations change the bundle identity, which `compare` correctly refuses. The adapter uses `@docxodus/export`'s public PDF API, requires the source-bound build record, verifies input and output digests, retains the production report, uses configured fonts, and keeps Chromium's process sandbox. It never silently uses an unrecorded distribution directory. On a host without the required sandbox, the result is unmeasured, not a claimed rendering failure.

`BENCH_LIBREOFFICE` can select an explicit LibreOffice executable. All tool versions and binary hashes, font hashes, reference PDF hashes, profiles, metric version, and suite identity are recorded. Retain `bundle.json` and its PDFs together; comparisons against a different reference bundle are rejected. Reference regeneration can change PDF metadata and therefore creates a new bundle identity.

For the two legacy page-number cases, the unit-valued row-height cases and the boundary merge, [equivalent-control references](docs/REFERENCE_CONTROLS.md) register the paired complex decimal PAGE and whole-twip captures from PRs #7 and #12 in a distinct `libreoffice-equivalent-controls` track. The original candidate inputs, complete token inventories, and assertions are preserved; the source bundle and direct captures remain available in the evidence.

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

`core-v32` adds a document-builder style-ID collision and a distinct-ID control for
[Docxodus #1186](https://github.com/JSv4/Docxodus/issues/1186). Each has two original source
documents and an independently authored composite reference. The candidate must build the pair
before PDF rendering; raster comparison measures the blue paragraph and larger red character
style while token inventories retain both sources. See the [preparation protocol](docs/ADAPTERS.md)
for the additional native build. All 143 previous PDF inputs remain unchanged. Reference
registration and full-suite scoring are pending.

## Redline track

The comparison track asks whether a redline is exactly reversible. Each of its 80 authored cases gives a candidate a document pair (or a base and two reviewers, or one document carrying tracked changes) and declares what accept-all and reject-all must produce. The benchmark accepts and rejects the candidate's output with its own revision engine, compared on a semantic view of text, field characters, bookmark and comment markers, note references and paragraph styles, and with LibreOffice's accept-all/reject-all through headless UNO, compared on text. It also checks that the package adds no Open XML SDK validation errors and satisfies declared structural assertions, such as unique style ids, valid paragraph ids, untouched unchanged text and a folded paragraph count. A case scores 100 only when everything holds. Every reproducer, for Docxodus issues #1165, #1166, #1167, #1170, #1174, #1175, #1176, #1183 and #1184 and for one bookmark-placement defect found while authoring the suite, has a control without the trigger, and an authored-redline calibration must score 100.

```sh
python3 -m bench redline build-validator --out /path/to/validator
python3 -m bench redline build-docxodus --source /path/to/Docxodus --commit FULL_COMMIT_SHA --out /path/to/adapter
python3 -m bench redline run --adapter docxodus --candidate FULL_COMMIT_SHA \
  --build /path/to/adapter --validator /path/to/validator --out runs/redline
```

Read [the redline scoring contract](docs/REDLINE.md) for the checks, the view, LibreOffice's limits and the eligibility rule.

## Word capture later

Use an authenticated Word export route to convert the exact registered inputs, preserve the original PDFs, and record input/PDF digests, provider, method, reported build (explicitly `null` if unavailable), platform, capture date, final/hidden review profile, approved artifact rights, and the exact font contract. Supply each PDF as `CASE_ID.pdf` and register the operator-reviewed capture:

```sh
python3 -m bench reference import --metadata capture.json \
  --pdf-dir /path/to/captured-pdfs --out references/word-v1
```

The metadata format is documented in [Word capture](docs/WORD_CAPTURE.md). Each Word track, including the provider-neutral `word` track, remains distinct from the LibreOffice tracks and from the others. A missing or ineligible capture blocks a complete Word suite score.

`core-v33` adds grouped paragraph borders in headers, footers, footnotes and endnotes,
with matching unbordered controls for [Docxodus #1203](https://github.com/JSv4/Docxodus/issues/1203).
Each card includes two adjacent bordered paragraphs and an unbordered paragraph. The body card
is a control for the same grouping mechanism. All 145 earlier inputs are unchanged. Reference
registration and full-suite scoring are pending.

`core-v35` adds final and original PDF views of an edited hyperlink containing inline custom XML
for Docxodus #1188, plus plain-hyperlink controls. Each candidate must compare the original
source pair before export. `redline-v2` adds the same trigger/control to independent
accept/reject scoring. All preceding PDF and redline input bytes remain unchanged.

The [completed #1188 run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/39155544679)
measures Docxodus `f4c0617`: all four new PDF views pass mandatory checks and score 99.648–99.654,
with calibration 100. Both new redline cases score 100 (original main: defect 0, control 100).
The archived run used the 153-case development registry before the Times New Roman case merged;
its full score is 87.216 with 143/153 mandatory passes. This branch retains that new font case
and all 150 preceding inputs unchanged, for 154 PDF cases. The four #1188 input pairs and
expected documents are byte-identical to the measured run; the archived score is not a full
154-case score. Candidate/reference screenshots for every new view are in the run's
`rendering-evidence` attachment.

`core-v37` adds ten final/original PDF views for one-sided comment wrappers (#1195) and reviewer-added comments (#1196), with five corresponding independent redline cases and controls. Candidate preparation invokes comparison or consolidation before production export. PDF comments are hidden, so PDFs measure body text/layout; the redline track independently checks comment range positions, references, definitions and reviewer revisions. All 154 preceding PDF inputs and 39 preceding redline input sets remain unchanged. New reference calibration and candidate scoring are pending.

`core-v38` adds eight final/original PDF views and four independent redline cases for #1197.
Invalid repeated references inside replaced content-control/custom-XML wrappers must resolve to one
comment, as in the valid-reference controls. PDF checks retain body content/layout; redline checks
verify exact comment definitions and anchors. All preceding packages remain byte-identical.

`core-v39` adds a keep-with-next heading followed by a splittable long paragraph and a keep-lines
control (#1182). Marker assertions require the heading and first body line together on the original
page for the reproducer, on the next page for the control, and retain every line of both documents.

`core-v40` adds an original exact-height header row whose hidden paragraphs cross the header band, plus a wider-band control for [Docxodus #1200](https://github.com/JSv4/Docxodus/issues/1200). The visible inventory is exact; bounded `clippedTokens` allow whole hidden words or their absence while rejecting partial glyph fragments. Metric contract 3 records this explicit rule. All 180 prior PDF inputs remain byte-identical. Full reference registration and scoring are pending.
