`core-v151` adds eight line-content cases for Docxodus #1565 and #1567: empty break lines,
an 18pt list number, a centered lead label and a mapped Symbol bullet, each with a control.
Slots follow native Word's per-line rule. See [the Word evidence and labeled renders](docs/results/line-content-height/README.md).

`redline-v39` adds three math cases for Docxodus #1189: a fraction whose control character was
inserted and then deleted is removed by Accept All and by Reject All, as in Word 2024. Two use the
`accept` operation and one `reject`. See [evidence](docs/results/math-control-revisions/README.md).

`redline-v38` adds eight cell-revision cases for Docxodus #1694: a deleted cell whose own paragraph
mark is tracked as deleted, accepted through the session and through `RevisionProcessor`. Word
leaves the row one cell short; each control deletes only the cell's run, where Word widens the
neighbour. See [the redline notes](docs/REDLINE.md#a-deleted-cell-whose-paragraph-mark-is-deleted-docxodus-1694).

`redline-v37` adds twenty cell-revision cases for Docxodus #1688: rejected cell insertions, rows and
a table whose every cell leaves, and `RevisionProcessor` accepting a deleted first cell and a
deleted cell inside a content control, each beside a control. A new `accept` operation mirrors
`reject`. See [the redline notes](docs/REDLINE.md#cells-that-leave-a-row-docxodus-1688).

`redline-v36` adds twelve cell-revision cases for Docxodus #1404: a tracked deletion of a row's
first or middle cell, and tracked deletions and an insertion on cells wrapped in their own content
controls, each resolved in bulk through the public session and each with a bare-cell
control that resolved before the fix. Expected geometry is what desktop Word 2024 writes. See [the redline notes](docs/REDLINE.md#session-revision-resolution).

`redline-v35` adds a document-default spacing reproducer and a `Normal`-style control for
Docxodus #1576, with a `style-run-history` check: Word's Reject All resets a style's run
properties when its spacing revision has no `w:rPrChange`. See [evidence](docs/results/default-spacing-history/README.md).

`redline-v33` adds revised running stories before deleted section boundaries, first-page flags,
and a retained-paragraph control for Docxodus #1555. See [evidence](docs/results/revised-section-stories/README.md).

`core-v103` adds four exact-spacing justification cases for Docxodus #1524. Native Word confirms
that mode 15 justified text can fit a bounded compressed line while legacy and left-aligned
controls retain natural wrapping. See [native comparisons and diagnostic limits](docs/results/exact-justification/README.md).

# DOCX fidelity bench

`core-v153` adds six original Sorrel tall-row cases for Docxodus #1558: a row whose minimum height
is taller than the page (exact-height control), a minimum-height row its 70 lines make taller than
a page (no-height control), and a tall row with centered cells (top-aligned control). Word 2024
adjudicates each marker's page and box. LibreOffice references are pending. See
[the Word measurements and labeled renders](docs/results/tall-rows/README.md).

`core-v154` adds three original Mariner cases for Docxodus #1559 and #1577, rendered with the All
Markup balloon layout (`commentColumnPlacement: "balloons"`). One comment marks the first line of a
Letter page and of an A4 page. Word 2024's Save as PDF zooms each page and its 3.7in markup area
by the 1/600 step nearest the paper's width over theirs (455 and 452) and centres the shrunken page
on the paper. `marker-region` assertions therefore hold the commented line and its `Commented`
label in the bands Word prints. The control has nothing for the balloons and prints at full size.
References and Word captures are pending.

`core-v152` adds eleven original Hazel text-placement cases for Docxodus #1550 and #1562: the
justified Hazel prose with no stated spacing, a bold word, a hyperlinked word, a numbered item
and a table cell, with left-aligned controls, plus kerning with a bold word, `w:kern` 0 and a
`w:kern` minimum equal to the text size. Word 2024 confirms every expected line. See
[the Word measurements and limits](docs/results/text-placement/README.md).
It also adds two original Thistle cases for Docxodus #1571: 51 double-spaced lines in 23 full
pitches plus 15pt, where the 24th line's text fits, and plus 13pt, where it does not. Word 2024
puts 24 and 23 lines on page 1 ([evidence](docs/results/last-line-leading/README.md)).

`core-v150` adds an embedded-font input and an unused-face control for Docxodus #1575. Both packages
embed an original Liatris program, obfuscated with its `w:fontKey`; cases list such families in
`embeddedFonts`, which the host never provisions. LibreOffice references are pending. See
[the evidence and limits](docs/results/embedded-fonts/README.md).

`core-v155` adds three automatic paragraph spacing inputs with flag-free controls and a contextual
spacing pair for Docxodus #1553: the document's first paragraph, a table cell, a paragraph beside a table,
and contextual spacing on either side of a 5pt/14pt boundary. Regions are Word 2024's word boxes.
LibreOffice references are pending. See [the evidence and limits](docs/results/automatic-spacing/README.md).

`core-v149` adds four fractional whole-number measure inputs and whole-value controls for
Docxodus #1622: border `w:sz="4.5"` in paragraph, table and cell borders, and `w:gridCol w:w="4000.5"`.
Word 2024 truncates each value. LibreOffice references are pending. See [the evidence and limits](docs/results/fractional-measures/README.md).

`core-v163` adds six inputs and controls for Docxodus #1692, each about the box around bordered
paragraphs: a `w:between` rule between the paragraphs of a box, the same beside a paragraph that has
none, contextual spacing across the edge of the box, `w:pageBreakBefore` and `w:keepNext` on a
bordered paragraph, and shading, which Word 2024 fills to the border. Each control drops only the
property under test. Regions are each label's line slot and page, which hold Word 2024's word boxes;
the shading pair declares the fill Word paints. LibreOffice references are pending. See
[the evidence and limits](docs/results/bordered-paragraph-spacing/README.md).

`core-v162` adds four inputs and controls for Docxodus #1677: a bordered paragraph with 14pt before
and after between other paragraphs, three such paragraphs sharing one box, the first under
`w:doNotUseHTMLParagraphAutoSpacing`, and one moved to the top of page 2. Word 2024 draws the border
around the text only, so the spacing lies outside the box and collapses, adds or drops as an
unbordered paragraph's does. Each control drops only the border. Regions are each label's line slot
and page, which hold Word 2024's word boxes. LibreOffice references are pending. See
[the evidence and limits](docs/results/bordered-paragraph-spacing/README.md).

`core-v161` adds three inputs and controls for Docxodus #1551: three labels a paragraph split by
line breaks on an 18pt line grid, which Word 2024 puts on the grid as it does wrapped lines (18pt,
36 a page), the same at 20pt at-least spacing, where Word puts the minimum's surplus above the grid
lines, and a 24pt word after each 12pt label at 0.8 lines, which Word lays out on the grid as at
single spacing (36pt). The first two controls drop only the grid; the third keeps the grid and
drops the multiple. Regions are the band each line's text occupies, and they hold Word 2024's word
boxes. LibreOffice references are pending. See [the evidence and limits](docs/results/single-line-grid/README.md).

`core-v160` adds three inputs and controls for Docxodus #1551: a bold word after each label and a
24pt word after each 12pt label on an 18pt line grid, which Word 2024 gives the grid lines their
tallest text needs (18pt and 36pt), and 1.5-line spacing on the grid, where Word centres each
line's text in its 27pt line. Each control drops only the grid. Regions are the band each line's
text occupies, so they also test where the text sits, and they hold Word 2024's word boxes.
LibreOffice references are pending. See [the evidence and limits](docs/results/single-line-grid/README.md).

`core-v159` adds two inputs and controls for Docxodus #1551: 24pt text with 30pt at-least spacing
on an 18pt line grid, which Word 2024 gives the two grid lines its text needs (36pt, 18 a page),
and a tracked deletion shown in every paragraph, printed in markup, which Word keeps on its 18pt
grid line. Each control drops only the grid. Regions are each label's line slot and page, which hold
Word 2024's word boxes. LibreOffice references are pending. See [the evidence and limits](docs/results/single-line-grid/README.md).

`core-v158` adds two inputs and controls for Docxodus #1551: 15pt at-least lines on an 18pt line
grid, which Word 2024 gives whole 18pt lines (36 a page), and one line before in a document with a
tracked insertion, printed in markup, which Word counts as one 18pt pitch on the grid. Each control
drops only the grid. Regions are each label's line slot and page, which hold Word 2024's word boxes.
LibreOffice references are pending. See [the evidence and limits](docs/results/single-line-grid/README.md).

`core-v157` adds two inputs and controls for Docxodus #1553: 14pt after and 14pt before under
`w:doNotUseHTMLParagraphAutoSpacing`, which Word 2024 adds to 28pt (the control drops only the setting),
and automatic spacing in a two-paragraph header, 14pt after its last paragraph included (the control
drops only the flags). Regions are Word 2024's word boxes. LibreOffice references are pending. See
[the evidence and limits](docs/results/automatic-spacing/README.md).

`core-v156` adds four empty section-mark inputs and controls for Docxodus #1572: an empty
paragraph that only carries a section break, before a continuous, a spaced and a two-column
section, and after page breaks. Word 2024 sets the mark on the preceding line, so each control
carries the same break on that line. LibreOffice references are pending. See [the evidence and limits](docs/results/section-marks/README.md).

`core-v144` adds a three-section default-story inheritance case and explicit-reference
control for Docxodus #1619. PDF checks preserve the paginated story behavior while product
tests assert flow selection. See [all-page native previews and limits](docs/results/flow-story-inheritance/README.md).

`core-v143` adds a split-run input and whole-run control for Docxodus #1624.
These check preserved PDF content, formatting and placement; flow-HTML span coalescing
is asserted by the product's DOM regressions. See [the labeled native previews and limits](docs/results/text-spans/README.md).

`core-v137` adds six manual text-width cases for Docxodus #1564: expansion, compression,
contiguous and separate IDs, paragraph continuation, and an unchanged ordinary-text control.
All 1012 prior document inputs are unchanged. See the
[labeled comparisons, exact glyph checks and diagnostic limits](docs/results/manual-text-width/README.md).

`core-v136` adds six short/continued footnote percentage-width cases and two independent
footer-rounding controls for Docxodus #1564. All 1004 prior inputs are unchanged.
The long 100% note retains its existing pitch diagnostics; see
[the labeled comparisons and limits](docs/results/footnote-character-width/README.md).

`core-v102` adds six original paragraph-fragmentation cases for Docxodus #1521. The tracked/textbox
matrix and four-page controls pin every line's page and region. All 738 previous inputs are unchanged.
See [all six labeled comparisons and diagnostic limits](docs/results/paragraph-fragmentation/README.md).

`redline-v29` adds empty running stories in inserted opening sections and a stable-section
control. See [evidence](docs/results/inserted-section-stories/README.md).

`redline-v28` adds complete-rewrite diagnostics for articles, list numbers and linked
articles, plus a distinct-word control. See [evidence](docs/results/complete-rewrites/README.md).

`redline-v27` adds two unchanged-field/default-spacing reproductions and a literal-text
control for [Docxodus #1533](https://github.com/JSv4/Docxodus/issues/1533). Effective spacing
is checked after independent acceptance and rejection; text alone cannot pass these cases.
See [the review evidence](docs/results/field-default-spacing/README.md). Existing fixture
bytes and the PDF track are unchanged.

`core-v101` adds 14 original review-visibility cases for Docxodus #1523. Formatting-only,
comment-only and combined controls accompany all eight combinations of formatting,
text-revision and comment visibility. Native PDFs with comments hidden retain the layout comparison;
independent delivered-HTML observations and printed companions check the requested policy.
All 724 prior document inputs are unchanged.
[All 14 labeled comparisons](docs/results/review-visibility/README.md) show the native primary
profile and the default/requested candidate review display.

`core-v100` adds nine original fractional-table-border cases for Docxodus #1522:
quarter-, half-, one- and three-point rules, inherited styles, merged shared segments,
wrapping boundaries and a borderless control. The opt-in `colored-rule-widths` check
reads physical vector widths independently of the 96-DPI raster, whose pixel grid can
hide subpixel differences. Existing raster scoring and all 715 prior inputs are unchanged.
[All nine labeled comparisons](docs/results/fractional-table-borders/README.md) include full pages and table crops.

`core-v99` adds eight original DrawingML-group cases for Docxodus #1527: independent
header/body stories, nested and scaled coordinates, mixed picture/shape members, and
single/separate controls. [All eight labeled comparisons](docs/results/drawingml-group-stories/README.md)
include complete token inventories and explicit baseline refusal panels.

`core-v96` adds eight original frame-clearance cases for Docxodus #1510: four native
preceding-text/page-end reproducers and four matched zero-distance controls. Complete token
inventories and Word-adjudicated marker regions preserve fixed frame paint and page ownership.
[All eight labeled comparisons](docs/results/frame-clearance/README.md) record native font substitution.

`core-v95` adds seven original inline-frame interval cases for Docxodus #1509: centered,
interior, right and page-relative wrapping with below-frame, unwrapped and ordinary-flow
controls. Complete token inventories and Word-adjudicated position checks preserve both
available intervals.

`core-v94` adds five endnote-comment export cases for Docxodus #1505: long single
paragraphs, multiple paragraphs, nested replies, and short controls. They reuse the
original Maple inputs and require every body and comment word in the printed companion.

`core-v93` adds 30 original inline-frame cases for Docxodus #1487, with body, header,
footer, cell, page-end, separate-carrier, edge-distance and header-overhang controls. The versioned
`non-overlapping-markers` check detects overprinted labels while allowing native Word's
beside-frame layout and LibreOffice's ordinary paragraph flow. Complete inventories,
page/position bounds and raster comparisons still apply. All 645 prior inputs and case
declarations are preserved apart from their shared generator hash. [All 30 cases and labeled local comparisons](docs/results/inline-frames/README.md)
include completed production comparisons: candidate 30/30 versus main 15/30 mandatory checks, with 15 unchanged controls. These cases do not claim exact Word raster parity.

`core-v92` adds twelve original textbox-fit cases for Docxodus #1492, covering omitted fit,
theme defaults, local precedence and running stories. [All twelve cases and labeled previews](docs/results/textbox-fit/README.md)
retain complete token inventories and independent visible-label bounds. All native references
are eligible; completed production measurements and their full-page previews are linked there.

`core-v91` adds thirteen original bordered-footnote cases for Docxodus #1491, covering two- and
three-page notes, box and bottom borders, kept paragraphs, headings, table cells and controls. Complete
source-token inventories remain mandatory. [All thirteen cases and labeled previews](docs/results/bordered-footnotes/README.md)
distinguish eleven eligible LibreOffice references from two incomplete table references that
remain unscored. Production measurements of the eleven eligible cases are complete and linked there.

`core-v90` adds seven original complete-comment PDF cases for Docxodus #1490. A separate
print profile checks source text, paint, bounds and paper geometry while the primary hidden-comment
PDF retains its native layout comparison. [All seven cases and labeled previews](docs/results/complete-margin-comments/README.md)
separate local diagnostics from completed production-runtime measurements.

`core-v86` adds ten original TIFF/WMF image cases and PNG controls for Docxodus #1484.
Independent per-color bounds and paint coverage checks cover both figures, image sizing,
headers and VML groups. [Native diagnostic evidence and all ten previews](docs/results/static-images/README.md)
record Word/LibreOffice differences and the pending production-export measurements.

`core-v78` adds an authored natural-line-height reproducer and exact-height control for
[Firefox page-view overlap](docs/results/firefox-line-height/README.md) (Docxodus #1424).
The fixtures are in the PDF track; a separate browser diagnostic checks their glyph overlap
and complete text in Firefox and Chromium. Existing input bytes and assertions are unchanged.

`redline-v21` adds Compare and Consolidate moved-paragraph reproducers for Docxodus #1420 and
ordinary replacement controls. A structural assertion checks moved and deleted text carriers;
accept/reject and schema checks remain mandatory. [LibreOffice and Word Online previews](docs/results/move-from-text/README.md)
show the local outputs; Word Online opens both baseline and fixed output.

An [unweighted font diagnostic](docs/FONT_DIAGNOSTICS.md) covers actual fallback-face
observations, unused declarations and per-page request attribution. It independently reads
font names from produced PDFs and keeps missing-font warnings and verification status intact.

An additional [unweighted editor browser diagnostic](docs/editor/README.md) covers review
counts/targets, tab caret movement and native plain/rich clipboard actions with ten original
reproducer/control inputs. [Labeled before/after evidence](docs/results/editor-review-tabs/README.md)
records five baseline failures, five passing controls and ten candidate passes. The PDF and
redline suites and their metrics are unchanged.

`core-v77` adds 37 independently authored positioned-story, tab, textbox and wrapping cases.
The new fixed-box clipping contract derives optional words only from conservative source geometry
and exact paragraph lines; candidate-reported clipping never grants an exemption. All 496 previous
inputs and case assertions remain unchanged apart from shared generator hashes.
[Focused evidence](docs/results/export-story-contexts/README.md) separates original failures,
composition regressions, explicit warning/strict-policy outcomes and reference limitations.

`core-v76` adds 40 independently authored paragraph, table, textbox and inline-object cases.
They cover automatic spacing, both tab carriers, bookmarked and merged tables, impossible
cell keeps, inherited frame defaults, signed wrap clearances, floating pictures, and stable
warning identities for deliberately undecodable repeated header images. All 456 prior input
bytes and assertions are preserved; only shared generator hashes change.
[Focused diagnostic evidence](docs/results/export-inline-contexts/README.md) records exact
renderer revisions and explicit placeholder/reference limitations without a fidelity score.

`core-v75` adds 28 independently authored continuation and geometry cases, with an unchanged
DrawingML background control reused in the focused set. Cases cover border-style reopening,
inline and floating pictures, off-paper shapes and blank boxes, zero-font marks, promoted frames,
text-box contextual spacing, and over-wide running-story tables. All 428 previous DOCX inputs
and case assertions remain unchanged; shared generator hashes are refreshed.
[Focused review evidence](docs/results/export-reliability-continuations/README.md) records exact
source identities, public-API checks, bitmap inventories, and reference limitations without
claiming a full-suite fidelity score.

`core-v74` adds 34 independently authored export-reliability cases and controls: running-story
spacing and margin cells, unpainted source carriers, fixed-textbox blank lines, oversized paragraphs
and cells, citing tables, unused XML, fractional twips, table width, and header background pictures. All 394 previous DOCX
inputs remain byte-identical. [Focused evidence and qualifications](docs/results/export-reliability/README.md)
distinguish public-API availability checks from registered references and fidelity scores.

`core-v73` adds six original nested-inline rendering cases for Docxodus #1410: 64 hyperlinks,
simple fields, or mixed hyperlink/control/custom-XML wrappers, each with a flat-text control.
They retain the existing 120-second conversion deadline and all PDF checks. All six inputs are
schema-clean; all prior DOCX bytes and the `redline-v20` corpus remain unchanged. Focused CI
measurements use a distinct diagnostic suite identity; default measurement still covers both
complete tracks.
[Measured before/after results and all six labeled previews](docs/results/nested-inline-render/README.md)
record three baseline readiness failures and six candidate PDFs with all mandatory checks passing.
The focused score is 49.99744 → 98.58696; the mixed case remains 91.72840.

`redline-v20` adds fourteen original paragraph-rewrite cases for Docxodus #1406: unchanged echoes
and outside edits around bound/citation controls, plus formatted multiline echoes. Each has an
ordinary-text control. Native control subtrees, including binding paths/store ids and field instructions, are checked exactly;
raw candidates must have no revisions. Existing semantic, schema and LibreOffice checks remain
mandatory. See [the contract](docs/REDLINE.md#whole-paragraph-control-preservation). All prior DOCX
bytes and eligibility declarations remain unchanged; the PDF suite stays `core-v72`.

`redline-v19` adds twenty original visible-text span cases for Docxodus #1387/#1409: native tabs, breaks, carriage returns, positional tabs, hyphens and symbols, plus inline custom XML, each with an ordinary-text control. Accepted/rejected native atom names and every Word attribute are checked exactly, alongside existing semantic and schema checks. Three newly authored LibreOffice views are narrowly ineligible after schema-clean, fresh-profile calibration; all other views remain mandatory. See [scope and qualifications](docs/REDLINE.md#visible-run-atoms-and-inline-xml) and [all labeled review previews](docs/results/visible-atoms/README.md). All prior DOCX bytes and eligibility declarations remain unchanged; the PDF suite stays `core-v72`.

`core-v72` and `redline-v18` add package-shape cases for Docxodus #1384 and #1388. Four PDF inputs pair a well-formed control with an embedded-font part that has no content type, a glossary typed only as generic XML, and an external hyperlink reusing the settings relationship's id; the Open XML SDK refuses all three at open. Eight redline cases (a new `packages` category) compare those packages, and a multi-recipient `mailto:` link target that `System.Uri` rejects, against a revision with one added paragraph, each with a control; a new `hyperlink-targets` assertion requires link targets to survive exactly as written. The asset audit now permits exactly two shapes these cases need: reserved `example.com` hyperlink targets and a placeholder (not a font program) at an embedded-font relationship. The validator now opens an in-memory copy of a temporary copy, since the SDK otherwise writes a rewritten link target back into the file it validates, and an output the SDK cannot open always fails validity, even when its inputs cannot be opened either. All prior DOCX bytes are unchanged. See [the redline notes](docs/REDLINE.md#package-shapes-and-external-link-targets-docxodus-1384-1388) and [the labelled sheets](docs/results/package-shapes/).

`core-v71` adds three independently captured Word baseline and word-advance controls for Docxodus #1124: 40 paragraphs covering two fonts, new sizes, spacing multiples and ordinary-space alignment. See [native/candidate evidence and provider qualifications](docs/results/native-text-precision/README.md). All 381 prior PDF inputs and the historical CI suite are unchanged.

`core-v70` adds two independently captured Word justification controls for Docxodus #1124, covering 45 held-out paragraphs at 11pt and 12pt. See [all native/candidate pages and measurement qualifications](docs/results/justification-lines/README.md). The 379 prior PDF inputs and historical CI suite are preserved.

An independent MIT benchmark of delivered PDF rendering and of document comparison. The harness and every input document are authored in this repository. It measures layout, visible content, physical pages, fonts, and declared feature assertions. It produces portable HTML evidence and JSON measurements.

The initial reference track is **LibreOffice**, pinned in CI to 25.8.7.3. Word reference PDFs can be registered as separate tracks. The current PDF suite is `core-v74`, with report-only renderer CI. A separate comparison track, `redline-v18`, scores redlines on accept/reject round trips; see [Redline track](#redline-track). Close-match thresholds have not been calibrated as release gates.

`redline-v16` added seven original reviewer-account cases for Docxodus #1317: namesakes with a different or absent account, principal-name and object-id aliases, a legacy control, and the first revision/comment under a free name. Public name-status queries, exact reviewer metadata and retained insertion/deletion markup supplement independent round trips and schema checks. All prior DOCX bytes remain unchanged; the PDF suite stayed `core-v62`.

`core-v69` adds fourteen original kept-note paragraph controls for Docxodus #1217: ten mode/widow neighbors and four 120-line continuations with first/mid-page citations. Exact Word input hashes, complete token inventories and every body/note marker page are bound in [the evidence](docs/results/kept-note-paragraphs/README.md). The long controls expose the natural-line probe precision and first note-only fragment budget defects. All 1,051 earlier DOCX files, `redline-v17` and the historical twelve-case CI selection remain unchanged. Raw long wrapping probes remain diagnostic; the missing original carried-note input remains unresolved.

`core-v68` adds nineteen original kept-citation and dense footnote-chain cases for Docxodus #1217, with native Word keep/widow/separator controls. Every input matches its captured Word hash; complete inventories and every marker's page are asserted. [All-page evidence and qualification](docs/results/kept-note-flow/README.md) retain remaining raster differences and the unresolved carried/oversized-kept-note cases. All 1,032 prior DOCX files, `redline-v17` and the historical 12-case CI inputs are unchanged. Local candidate diagnostics are unscored.

`core-v67` adds eight font-aligned note-table flow cases for Docxodus #1217, reusing the existing author's nested/ordinary, long-row and wrapped two-cell construction. Native Word input hashes, page assertions and all-page comparison sheets are retained in [the evidence](docs/results/note-table-flow/README.md). All 1,024 prior DOCX inputs, `redline-v17` and the historical 12-case CI inputs remain unchanged. Local candidate comparisons are unscored; remaining #1217 items are explicit.

`core-v66` adds 13 independently generated Times New Roman oversized-block cases for Docxodus #1202. They cover exact rows, header and nested tables, bordered paragraph continuations, physical paper clipping, footer overlap, and required blank final pages. All 1,012 earlier DOCX files remain byte-identical; `redline-v17` and the historical 12-case `core-ci-v2` inputs are unchanged. Native Word captures and labelled before/after diagnostic sheets are recorded in [the evidence](docs/results/oversized-page-blocks/README.md).

`core-v65` adds 19 original Times New Roman table-placement cases for Docxodus #1219 and #1244: eight margin/indent cases, five paragraph/table boundary controls, and six legacy layout controls. All 992 earlier DOCX files are byte-identical; `redline-v17` is unchanged. Native Word captures, renderer qualifications, unchanged residual differences, and screenshots are retained in [the evidence](docs/results/table-horizontal-placement/README.md). The original nested-table case now requires the two left-cell origins observed in Word, without changing its input.

`core-v64` adds the original Word-adjudicated Times New Roman zero-width column and 24pt control for Docxodus #1201. Both cover exact and at-least rows, borderless and bordered. All 990 prior DOCX files are byte-identical, and the `redline-v17` corpus is unchanged. Native Word references and unscored sandboxed export diagnostics are documented with the case evidence.

`core-v61` adds five story-comment cases for Docxodus #1310. Three reuse the original prepared inputs byte-for-byte: a footer comment, a footnote comment and a body-comment control. PDF profiles hide comments, keeping complete document-token/page checks. Two more cover a non-body range beside a real body comment reference, with a body-reference control. The delivered-HTML companion uses margin comments and requires all declared note text to be readable. These cases omit reference runs because LibreOffice cannot load the non-body reference shape; this is Docxodus's preservation contract, not a claim of Word behavior. Prior DOCX bytes and the redline suite remain unchanged.

`core-v60` adds eleven original literal-tab cases for Docxodus #1353: body, header, footer and mixed-text paragraphs, each with an explicit-tab control, plus literal/explicit tabs in visible deleted text and an untracked control. The marker must reach the right-hand part of the page; complete words, page geometry and unaligned raster measurements remain mandatory. The existing isolated-dot-leader policy is declared explicitly. Its source validator recognizes literal tabs in live/deleted text while keeping field instructions excluded; filtering and thresholds are unchanged. All prior DOCX bytes remain unchanged; the redline suite stays `redline-v15`.

`core-v59` adds four original table-property cases for Docxodus #1341. Final and original PDF profiles must preserve the independent widths, colored borders and cell margins of already adjacent tables. Each profile has a control with a paragraph separating the tables. Complete visible-token inventories, page checks and unaligned raster measurements remain in force. LibreOffice itself joins the adjacent pair using the second table's width and margins, so that reference is not proof of boundary preservation. The controls remain separate. This difference stays visible in the raster measurement; no reference eligibility or thresholds are relaxed. All prior DOCX bytes are unchanged; the redline suite stays `redline-v15`.

`redline-v15` adds eight original column-review cases for Docxodus #1330: leading/trailing omissions and mixed merged/omitted rows, with direct-edit controls. A tracked insertion must list one supported revision and resolve through the public bulk or selective API. Typed native outcomes, exact resolved table state and an empty registry/markup revision inventory are mandatory. All prior DOCX bytes remain unchanged; the PDF suite stays `core-v58`.

`redline-v14` adds sixteen original text-span cases for Docxodus #1337: tabs and line breaks between text nodes in one run, direct and tracked edits, and selections before or across the marker. Each reproducer has a control whose marker follows the edited text. Public span replacement must retain exact marker order through accept/reject. All prior DOCX bytes remain unchanged; the PDF suite stays `core-v58`.

`redline-v13` adds three original block-insertion reproducer/control pairs for Docxodus #1331. The public paragraph, horizontal-rule and table insertion APIs must refuse cell anchors before mutation or undo history, while body-paragraph anchors remain valid. Typed operation observations, exact unchanged table geometry, schema and text checks are mandatory. All prior DOCX bytes remain unchanged; the PDF suite stays `core-v58`.

`redline-v12` adds 20 original column-edit cases for Docxodus #1342: pending real/no-op grids, merged cells with pending shading, rows with pending height and omitted leading columns, and unit cells copied from merged references. Each reproducer has a revision-free control. Native insertion/deletion followed by bulk or selective revision resolution must match independently authored exact table states. All prior DOCX bytes remain unchanged; the PDF suite stays `core-v58`.

`redline-v11` adds full and partial tracked column-width edits for Docxodus #1322, each with an untracked control. The public session API must report one tracked revision (zero untracked), and independent assertions check grid, cell and table widths after accept/reject. All prior DOCX bytes remain unchanged. The PDF suite stays `core-v58`.

`redline-v10` adds a Strict self-comparison at exact raw package limits for Docxodus #1352 and its Transitional control. A mandatory semantic preflight runs with and without the package supplement before the ordinary redline round trips; missing or incorrect measurements fail the case. Earlier DOCX bytes remain unchanged. The PDF suite stays `core-v58`.

`core-v58` adds nine original leader-line cases for Docxodus #1285, each with an 864-twip right indent. `tabs-right-stop-pageref-field` holds the page numbers in `PAGEREF` complex fields to bookmarks on pages 2–5; `tabs-right-stop-pageref-control` has the same numbers as plain text. `tabs-right-stop-wrapped-title` has titles that wrap, so each page number belongs at the end of its title's last line; its control is `tabs-right-stop-in-right-indent`. `tabs-right-stop-second-stop-in-indent` puts a first right stop at 8800 twips, inside the right indent, followed by a right stop at 9360 or a left stop at 8900; `tabs-right-stop-second-stop-control` moves both before the line end. `tabs-right-stop-linked-bookmark` puts each entry in a hyperlink with its bookmark inside the link; `tabs-right-stop-linked-control` has no bookmarks. Title, last-title-word and page-number position assertions check every entry against the reference. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v9`.

`core-v57` adds three original leader-line cases for Docxodus #1275. Four entries each have a label, a left title stop, and a right dot-leader page-number stop at the column edge. In `tabs-right-stop-in-right-indent`, an 864-twip right indent ends each line before that stop. In `tabs-right-stop-inline-markup`, the entries carry an empty bookmark, a non-breaking hyphen, underlined tab runs and struck tab runs. `tabs-right-stop-plain-control` has neither. Title and page-number position assertions check that each entry stays on one line, with its number on the stop. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v9`.

`core-v56` adds five original inline-drawing cases for [Docxodus #1270](https://github.com/JSv4/Docxodus/issues/1270): a 144 by 72pt teal rectangle drawn as a plain DrawingML shape (`wps:wsp`, not a text box), the same rectangle as the only child of a group (`wpg:wgp`), each of these again inside a tracked deletion viewed in markup, and an inline teal picture of the same extent as the control. The rectangle is the only ink between two text paragraphs. Raster scores measure the rectangle, and a placement assertion requires the following paragraph to start below the rectangle's 72pt line. LibreOffice 25.8.7.3 draws the rectangle in all five cases, deleted ones with a change bar. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v9`.

`core-v55` adds an original pair for Docxodus #1271, measured in markup view: a one-line 10pt footnote whose only run carries a pending formatting revision (`w:rPrChange`, italic removed), and a control without the revision; the inputs differ only in that element. Docxodus's default markup presentation underlines a revised run with a border, which hung below the note band, and its export refused the whole document as a clipped footnote. Each case requires the note's first word, `NoteQuartz`, in the footnote area of page 1 and on the citing line's page; the complete token inventory requires the whole note. LibreOffice 25.8.7.3 renders both notes in full on page 1. Word adjudication is pending: Word reference PDFs of the exact inputs have not been captured. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v9`.

`core-v54` adds an original deleted-field pair for Docxodus #1272: a three-page running story whose footer line, "Sheet N of 3", is built from complex PAGE and NUMPAGES fields inside a tracked deletion (so their instructions are `w:delInstrText`), and a control with the same footer left undeleted. Both are measured in markup view, where the struck footer stays visible. Both fields cache the result 1, so the inventory (one 1, one 2, four 3s) and the page-1 and page-2 number placements fail a renderer that prints a cached result instead of the page's own number. LibreOffice 25.8.7.3 shows the deletion and advances both fields, and its direct captures of both cases are eligible. Word adjudication is pending: Word reference PDFs of the exact inputs have not been captured. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v9`.

`redline-v9` adds an original reply-parent trio for Docxodus #1312: the revision adds a threaded reply to an unchanged comment, and the original gives that comment no paragraph id and no commentsExtended part, or a different paragraph id from the revision's; the control gives the comment the same paragraph id in both. A new `comment-threads` assertion requires the redline's reply to name its parent comment's paragraph id and every parent to have its own commentsExtended entry; neither round-trip view reads comment threading. LibreOffice 25.8.7.3 shows no revision for a reply whose markers are the only change and keeps it on reject, so its comparisons are declared ineligible for all three. Earlier DOCX inputs are byte-identical. (`redline-v8` is claimed by open bench PR #79; whichever merges second is renumbered at merge.)

`core-v52` adds two original pairs for Docxodus #1314, each a reproducer and a control that differ only by a pending tracked section-property change (`w:sectPrChange`) on the final section, measured in markup view. The first pair is about endnote format: an endnote under a section whose pending tracked property change (`w:sectPrChange`) stores earlier properties that numbered endnotes in decimal, and a control with the same section and no pending change. The current section declares no endnote format, so the document's lowerRoman setting applies and the citation and note both read `i`. Both are measured in markup view. The inventory (two `i`, no `1`) fails a renderer that reads the stored earlier properties as the section's own. LibreOffice 25.8.7.3 numbers both cases `i`, and its direct captures of both are eligible. The second pair is about a floating picture: a one-inch picture anchored 264pt from the page's left edge and square-wrapped on both sides, in an A4 section whose pending change stored earlier Letter properties. The picture's centre is right of the A4 page centre but left of the Letter one. A renderer that lays the section out on the stored Letter page moves the picture to the other side of the text. A `marker-region` assertion requires the paragraph's first word, `FloatLead`, to start at the left margin, beside the picture. LibreOffice 25.8.7.3 places it there in both cases, and its direct captures are eligible. Word adjudication is pending: Word reference PDFs of the exact inputs have not been captured. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v7`. (`core-v51` is #80's. Open bench PRs #78 and #82 also claim `core-v51` and are renumbered at merge, as is this suite if one of them lands first.)

`core-v51` adds three original single-paragraph cases for Docxodus #1269: three tabs on automatic stops under a 12-twip and a zero `w:defaultTabStop`, and a 720-twip control; the cases differ only in that setting. The lead text runs past the hundredth 12-twip stop. The control places `TabNorth`, `TabEast` and `TabSouth` within 0.5pt of the reference. A correct 12-twip tab advances under 0.6pt, so position cannot tell it from a dropped one; that case catches a conversion failure and a half-inch fallback. Each word must end before it would on the half-inch grid and start no more than 3pt left of the reference. A zero interval has no automatic stops: Word for the web gives each tab no width, while LibreOffice 25.8.7.3 uses its own 1.25cm default. The zero case therefore carries Word-adjudicated regions: each word must start no more than 3pt left of its zero-width position and at least 4pt before LibreOffice's stop. The [Word evidence](docs/results/default-tab-interval-word.md) comes from captures of the Docxodus issue's own inputs and is not a registered reference. Where a word lands on the fine grid, or beside the preceding word, depends on the renderer's text measurement, which the raster score measures. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v7`.

`core-v50` adds an original run-in pair for Docxodus #1294: three run-in sections whose headings (keepNext and keepLines, hidden paragraph mark) join the paragraph that follows, filling the end of a page, and a control whose headings carry no keep properties. The layout asserted is the behaviour Docxodus #1294 specifies, not a measured Word fact: a joined block keeps with the next block as its closing paragraph does, so two sections stay on page 1 and the third starts page 2. LibreOffice 25.8.7.3 applies the heading's keepNext to the whole block and chains all three sections onto page 2, so its direct capture fails the declared assertions; the `libreoffice-equivalent-controls` track captures the control instead, under a proof that the pair differs only in the headings' keep properties (see [Equivalent-control LibreOffice references](docs/REFERENCE_CONTROLS.md)). Word adjudication is pending: Word reference PDFs of the exact inputs have not been captured. Earlier DOCX bytes are unchanged. The redline suite remains `redline-v7`.

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

The [Markdown projection diagnostic](docs/results/markdown-shapes/README.md) checks exact public
`Project`/`ProjectAnchor` output for textboxes and content-control-wrapped table rows/cells.
Its fourteen original inputs and before/after screenshots are unweighted and separate from PDF/redline scores.
`projection-v2` adds four [raw-write tracking diagnostics](docs/results/raw-tracking/README.md)
for Docxodus #1625: insert/replace while recording and their explicit untracked controls.
Exact refusal results, complete package-part identity, history and saved-output schema are checked.
`projection-v3` adds seven [deleted-row reproducer/control pairs](docs/results/deleted-rows/README.md)
for Docxodus #1628, checking GFM headers/body, opaque dimensions, wrapped/merged rows,
wholly deleted tables and row-carried textboxes.
`projection-v4` adds two [tracked table-insertion pairs](docs/results/table-insert/README.md)
for Docxodus #1626: a table inserted while recording, before another table and at the end of
the body, each with an untracked control. Success, the public revision count, accept-all and
reject-all Markdown and history are checked.

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

Python 3.11 or newer is sufficient for the harness and tests; there are no Python package dependencies. Provision LibreOffice, Poppler (`pdftoppm`, `pdftotext`, `pdffonts`), qpdf 11 or newer, fontconfig, Liberation Serif, Times New Roman, and Arial separately. Times New Roman is required by the agreement variant, and Arial by the native baseline controls; on Ubuntu the rendering workflow provisions it through `ttf-mscorefonts-installer` under the font package's own license (see [RIGHTS.md](RIGHTS.md)). Docxodus requires font directories without symlinks: CI removes the installer's filename aliases, while local runs can use regular-file copies of the declared fonts and point fontconfig at that directory. Font hashes must still match the reference contract. To run Docxodus, also provision Node.js 22.13 or newer, .NET 10, its `wasm-tools` workload, and Chromium's sandbox host prerequisites.

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

Author a focused DOCX with original text and graphics, add a generator and rights record, declare all visible token counts and versioned assertions, and add its ID and primary category to a versioned suite. The runner discovers manifest records; no scoring change is needed to add a case. The current check registry supports `marker-region`, `same-page`, `non-overlapping-markers`, `marker-reference-position`, `color-geometry`, `color-reference-geometry` and `colored-rule-widths`; unknown types and versions are rejected. Region version 2 declares a 0.0001-point boundary tolerance for PDF coordinate serialization; version 1 retains exact boundaries. Reference-position checks compare a unique marker's page and top-left PDF position with its reference, within the declared tolerance in points. `non-overlapping-markers` version 1 names exactly two unique source tokens. Their extracted PDF word rectangles must have finite positive bounds on real pages, and must either occupy different pages or overlap by no more than the declared tolerance on at least one axis. The tolerance is limited to 0–0.5 pt to accommodate bounding-box rounding and adjacent-line font metrics. This checks selected word boxes, not full frame clearance or exact native wrapping; independent marker regions pin their pages and allowed positions. Missing or duplicated labels fail. New check implementations need positive and negative examples. The corpus generator is intentionally transparent and deterministic.

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

The comparison track asks whether a redline is exactly reversible. Each of its 216 authored cases gives a candidate a document pair (or a base and two reviewers, or one document carrying tracked changes) and declares what accept-all and reject-all must produce. The benchmark accepts and rejects the candidate's output with its own revision engine, compared on a semantic view of text, field characters, bookmark and comment markers, note references and paragraph styles, and with LibreOffice's accept-all/reject-all through headless UNO, compared on text. It also checks that the package adds no Open XML SDK validation errors and satisfies declared structural assertions, such as unique style ids, valid paragraph ids, untouched unchanged text and a folded paragraph count. A case scores 100 only when everything holds. Every reproducer, for Docxodus issues #1165, #1166, #1167, #1170, #1174, #1175, #1176, #1183 and #1184 and for one bookmark-placement defect found while authoring the suite, has a control without the trigger, and an authored-redline calibration must score 100.

```sh
python3 -m bench redline build-validator --out /path/to/validator
python3 -m bench redline build-docxodus --source /path/to/Docxodus --commit FULL_COMMIT_SHA --out /path/to/adapter
python3 -m bench redline run --adapter docxodus --candidate FULL_COMMIT_SHA \
  --build /path/to/adapter --validator /path/to/validator --out runs/redline
```

Read [the redline scoring contract](docs/REDLINE.md) for the checks, the view, LibreOffice's limits and the eligibility rule.

`redline-v25` adds an independently authored regrouped-textbox marker-gap reproducer and a separate-carrier control for [Docxodus #1428](https://github.com/JSv4/Docxodus/issues/1428). Exact marker order and carrier subtree checks pin a defect already repaired by the carrier identity fix. The previous 214 cases and their package bytes remain unchanged.

`redline-v24` adds bookmark addition/removal and unchanged-bookmark controls for [Docxodus #1426](https://github.com/JSv4/Docxodus/issues/1426). Both reviewers edit one paragraph beside an unchanged tab and equation. Ordered markers and selective reviewer resolution must agree with independently authored documents. The previous 210 cases and their package bytes remain unchanged.

`redline-v23` adds an original shared VML textbox geometry reproducer and a body-edit control for [Docxodus #1425](https://github.com/JSv4/Docxodus/issues/1425). Metric contract 14 extends exact resolved subtree checks to `w:pict`, so a text-only match cannot hide changed widths or lost textbox bodies. [Focused evidence and previews](docs/results/textbox-geometry/README.md) record the independent main/candidate measurements. All 208 previous cases and their package bytes remain unchanged; no full-suite score is claimed.

`redline-v22` adds ten original atomic-source cases for [Docxodus #1421](https://github.com/JSv4/Docxodus/issues/1421), including true two-reviewer consolidation and paired controls. Metric contract 13 adds exact resolved equation/drawing assertions. [Focused results and labeled previews](docs/results/atomic-source/README.md) show all five reproducers failing on main and all ten cases passing on the candidate. This is not a complete 208-case suite score; the authored LibreOffice calibration supports 5 of the 20 views.

The registered `core-ci-v2` selection preserves the 12 exact input hashes from the original rendering CI oracle. Its declarations include the Word-adjudicated nested-table margin checks. The full 346-case corpus remains the default; unknown selections and missing or changed historical inputs are rejected. Use the same selection for reference creation and every compared run:

```bash
python3 -m bench reference libreoffice --suite core-ci-v2 --out references/ci
python3 -m bench run --suite core-ci-v2 --reference references/ci/bundle.json --adapter libreoffice --candidate reference-calibration --out runs/ci-calibration --gate close
```

## Word capture later

Use an authenticated Word export route to convert the exact registered inputs, preserve the original PDFs, and record input/PDF digests, provider, method, reported build (explicitly `null` if unavailable), platform, capture date, final/hidden review profile, approved artifact rights, and the exact font contract. Supply each PDF as `CASE_ID.pdf` and register the operator-reviewed capture:

```sh
python3 -m bench reference import --metadata capture.json \
  --pdf-dir /path/to/captured-pdfs --out references/word-v1
```

The metadata format is documented in [Word capture](docs/WORD_CAPTURE.md). Each Word track, including the provider-neutral `word` track, remains distinct from the LibreOffice tracks and from the others. A missing or ineligible capture blocks a complete Word suite score.

An immutable external capture pack can supply its own `--manifest` to both `reference import` and `run`; the authored default corpus stays unchanged. Reviewed Word font aliases require exact source and PDF font-program bindings, as described in [Word capture](docs/WORD_CAPTURE.md). Results record the reference provider separately from the renderer's current `default` layout profile, and comparisons across either identity are rejected. This records the one existing layout mode; it does not add renderer profile options.

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

`core-v79` adds four endnote classification cases for [Docxodus #1485](https://github.com/JSv4/Docxodus/issues/1485): positive-id continuation notices, both separators, and a cited ordinary note. Exact PDF token inventories detect any leaked reserved text or marker. Existing fixture bytes remain unchanged.

`core-v80` adds five logical-grid vertical-merge cases for [Docxodus #1489](https://github.com/JSv4/Docxodus/issues/1489), including aligned, shifted, multi-column and omitted-leading-column cases on either row. Delivered-HTML assertions independently require rowspan=2 for the merged label; PDF assertions pin the merged label and the starter-row control to their expected columns; scoring also checks all text and table appearance. Existing fixture bytes remain unchanged.

`core-v106` adds five original table-page-remainder cases for [Docxodus #1569](https://github.com/JSv4/Docxodus/issues/1569). Three reproducers fill the current page through row/cell splitting; explicit row keeps and an unsplittable-cell control move intact. Exact production main/fixed builds pass 2/5 and 5/5 independent PDF checks; all five LibreOffice references qualify. The 755 prior input bytes remain unchanged. See the [full-page diagnostic evidence](docs/results/table-page-remainder/README.md); no Word parity or full-suite score is claimed.

`core-v107` adds eight original literal-line-ending cases for the newline portion of [Docxodus #1564](https://github.com/JSv4/Docxodus/issues/1564). Exact production main/fixed builds pass 3/8 and 8/8 mandatory PDF checks in explicitly permissive previews; strict-font delivery is separately recorded as 4/8 and 6/8. All eight LibreOffice references qualify. The prior 760 inputs are unchanged. See [full-page diagnostic evidence](docs/results/literal-line-endings/README.md); character scaling and fitted text remain open.

`core-v108` adds two original 3,000/6,000-entry ledgers for the font-observation budget in [Docxodus #1558](https://github.com/JSv4/Docxodus/issues/1558). The larger baseline export fails after layout; the fixed production export delivers all 6,000 entries across 112 pages with strict font checks and one explicit observation warning. The smaller control stays at 56 pages. All labels are checked on every page, with complete reports and labeled previews in [the diagnostic evidence](docs/results/font-observation-budget/README.md). Column failures remain open.

`core-v110` adds eight original page-break/paragraph-line cases for [Docxodus #1570](https://github.com/JSv4/Docxodus/issues/1570), including three unchanged controls and explicit paragraph-mark flag settings. See the [native references and exact-production diagnostics](docs/results/page-break-paragraphs/README.md). The previous 776 inputs remain unchanged; no metric or tolerance changes.

`core-v118` adds six plain OMML equation cases and two prose controls for [Docxodus #1554](https://github.com/JSv4/Docxodus/issues/1554).
Exact MathML structure, selectable PDF notation, whole-formula page membership and required-font presence
are independent source obligations. Strict public delivery improves from 2/8 to 8/8; native equation
references remain ineligible because LibreOffice substitutes the requested math face. The 844 prior
inputs remain unchanged. See [labeled screenshots and retained evidence](docs/results/plain-math/README.md);
no Word typography or full-suite score is claimed.

`core-v148` adds four original collection-font inputs for [Docxodus #1573](https://github.com/JSv4/Docxodus/issues/1573):
TTC/OTC-only families paired with standalone-font controls. Three tiny MIT font
programs are authored from geometric chevrons using the Python standard library;
no installed font is copied. Provision `fixtures/collection-fonts` through a scoped
fontconfig configuration for reference and candidate runs. The prior 1,062 DOCX
inputs are unchanged. [Capture notes and labeled sheets](docs/results/font-collections/README.md)
retain exact font identities and separate collection support from the opt-in local index.
