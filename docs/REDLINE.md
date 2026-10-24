# Redline track scoring

The redline track measures document comparison, not rendering. A candidate receives authored inputs and returns one package: a redline for a two-way comparison (`compare`) or an N-way consolidation (`consolidate`), or a resolved document for a revision operation (`reject`). The benchmark then asks one question of that package: do its tracked changes reproduce the declared documents exactly, and is the package sound?

The suite is `redline-v13`, in `fixtures/redline/manifest.json`. It is separate from the PDF suite and has its own version, digest and results. Like the PDF track it is report-only: CI records the measurement but gates nothing.

## Cases

`bench/redline_fixtures.py` authors every package from literal text and original OOXML. Regenerating it must reproduce every file byte for byte; `python3 -m bench.audit` and the tests check this. Each case records:

- `operation` and its `inputs`, each with a path, SHA-256 and role (`left`/`right`, `base`/`reviewer`, or the tracked `input`);
- `expected`: for `compare` and `consolidate`, the document accept-all must produce (`accepted`: the revised document, or for consolidation the authored merge of every reviewer's change) and the document reject-all must produce (`rejected`: the original or base); for `reject`, the `output` the operation must produce;
- `authored`: a redline (or resolved output) that is correct by construction, used for calibration;
- optional `reviewerExpected`: independently authored documents, with paths and SHA-256 digests, for every consolidation reviewer when conflict resolution or consensus attribution makes a selective result differ from an input; all selective comparisons remain mandatory;
- `assertions`: declared, versioned structural checks;
- `libreoffice`: for each expected document, whether LibreOffice can make that comparison (see below), with the reason when it cannot;
- `kind` (`reproducer`, `control` or `identity`), the Docxodus issue it pins, the rights record and the generator identity.

Every reproducer has a control: the same document shape without the trigger. Controls show that a failure belongs to the reported defect, not to the shape. Two identity cases calibrate the pipeline: a byte-identical pair, and a pair with equal content serialized with different run splits and revision-save ids, on which a comparison must report no change.

## Checks

A case scores **100** when every applicable check passes and **0** otherwise. There is no partial credit: a redline that is wrong on accept or reject is wrong. The evidence keeps a similarity ratio and a short diff for each failed comparison as diagnostics only.

1. **Conversion and integrity.** The candidate returns status `ok` with the output's digest. Its inputs are unchanged. The output opens as a package with one main document. The case's expected documents and authored redline are re-verified against the manifest digests when the case is scored. A known candidate failure (`failed`) scores zero; an unverifiable build or environment (`unmeasured`) blocks the suite score.
2. **Round trip through the benchmark's revision engine.** `bench/revisions.py` accepts every revision of the candidate's package and compares the result with `expected.accepted`, then rejects every revision and compares with `expected.rejected`. For `reject` cases, the candidate's output itself is compared with `expected.output`. This engine is written for this repository and shares no code with any candidate. It applies ECMA-376 Part 1 §17.13.5 markup directly:
   - accepting keeps `w:ins` and `w:moveTo` content and drops `w:del` and `w:moveFrom` content; rejecting does the reverse, restoring deleted text and field instructions;
   - a removed paragraph mark joins its paragraph to the next paragraph of the same container, whose properties the joined paragraph keeps; a removed mark with no following paragraph keeps its paragraph unless the paragraph is empty and not the last of the body or the only paragraph of a cell, note, comment or header;
   - row markers (`w:trPr/w:ins|del`), cell markers (`w:cellIns`/`w:cellDel`) and revision markers in a math run's properties are resolved; move range markers are dropped;
   - custom-XML insertion, deletion and move ranges resolve the enclosing tags independently of their content. One enclosing range or two ranges crossing the opening and closing tags can remove an envelope; untracked content and unrelated empty inline envelopes survive. Partial removal of only one tag is reported as unsupported rather than treated as a successful resolution (see [custom-XML range semantics](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.customxmlinsrangestart));
   - property-change records (`w:rPrChange`, `w:pPrChange`, `w:sectPrChange`, `w:tblPrChange`, `w:trPrChange`, `w:tcPrChange`, `w:tblGridChange`, `w:tblPrExChange`, `w:numberingChange`) are dropped on accept and restore the prior properties on reject;
   - a block content control or custom-XML element left with no content is removed, as is a table left with no rows.
   - For `consolidate`, attribution is checked too: accepting only one reviewer's revisions (by `w:author`) and rejecting every other revision must reproduce that reviewer's document, or the explicitly declared `reviewerExpected` projection. The bookmark-name cases declare the default base-wins policy: competing new ranges are absent, independent text edits survive, and a consensus range is credited to the first reviewer. These expectations are authored independently of candidate output and included in digest and regeneration audits.
3. **Round trip through LibreOffice.** `bench/lo_revisions.py` runs LibreOffice's own accept-all and reject-all (`.uno:AcceptAllTrackedChanges`, `.uno:RejectAllTrackedChanges`) through headless UNO, in a private profile and process, and saves the result with LibreOffice's Word filter. The expected document takes the same path, loaded and saved without an operation, so LibreOffice's import and export normalization applies equally to both sides. The two are compared on the text view. CI pins LibreOffice 25.8.7.3.
4. **Validity.** The pinned Open XML SDK validator (`tools/ooxml-validator`, DocumentFormat.OpenXml 3.5.1, file format `Microsoft365`) checks the candidate's package and every input. A finding counts by its error id, part and description; the package fails when any finding occurs more often than in every input. An XPath alone never distinguishes findings, so a moved error is not new and a duplicated one is. A run without the validator has no suite score.
5. **Declared assertions**, each versioned:
   - `untracked-text` v1 (scope `redline`): each listed text occurs in a paragraph of the declared `story` (`body`, or `headers` for every referenced header and footer) outside every `w:ins`, `w:del`, `w:moveFrom` and `w:moveTo`. A tracked span breaks the paragraph's untracked text, so text cannot be assembled across it, and text placed in a part the view does not read (an unreferenced comment, note or header) does not count. Cases list only text a correct redline leaves unchanged, so deleting and reinserting a whole document, which would otherwise pass both round trips, fails;
   - `paragraph-count` v1: the number of `w:p` in the body of the raw redline (scope `redline`). This is a minimality requirement, not reversibility: the #1183 cases use it to require that the revised document's paragraph folds into the deleted one, as Word's compare does;
   - `para-ids-valid` v1: every `w14:paraId` in every XML part is eight hexadecimal digits, below `0x80000000`, and unique across the package;
   - `style-ids-unique` v1: no two `w:style` elements share a `w:styleId`, whatever their types;
   - `comment-threads` v1 (scope `redline`): in the comments and commentsExtended parts, every entry is keyed to a comment's last-paragraph `w14:paraId`, every `w15:paraIdParent` names the last-paragraph `w14:paraId` of a comment that has its own entry, and for each declared `[reply, parent]` pair exactly one comment holds the reply's text and its entry names the comment holding the parent's text. Comment threading is not part of the semantic view, so neither round trip sees a reply detached from its parent;
   - `revision-count` v1: at most `max` revision records in the redline or output (scope `redline` or `output`); a `w:delText` or `w:delInstrText` outside any deletion also counts. Every `reject` case requires zero.

Unknown assertion types, versions or scopes are rejected when the registry is loaded.

## The semantic view

View version 1 is a JSON value with one entry per story:

- `body`; each header and footer as `section{n}:{header|footer}:{type}`, following the section's references; each note as `footnote{k}`/`endnote{k}`, numbered by first reference; each comment as `comment{k}`, numbered by first marker, with its author.
- Each story is a list of blocks in document order. A paragraph records its container path (`body/tbl0/tr1/tc0`, `body/sdt0`, `body/customXml0:element`), its paragraph style resolved to the style's type and name, and its inline tokens. A bookmark, comment range or permission marker between blocks is its own record at that position.
- Inline tokens are text (`w:t`, restored `w:delText`, tabs, breaks, hyphen characters), and markers: `field-begin`, `field-separate`, `field-end` and `field-instruction:…` for complex fields, `field-simple:…` for simple fields, `bookmark-start:NAME`/`bookmark-end:NAME`, `comment-start:k`/`comment-end:k`/`comment-reference:k`, note references and marks, objects, and the boundaries of inline content controls, custom-XML elements, hyperlinks, ruby and math zones. Field characters are therefore compared by count and order, bookmarks by name and position, comments by position and content.
- Revision ids, bookmark ids, comment ids, `w14:paraId`, revision-save ids and run boundaries are not part of the view. Character formatting and paragraph properties other than the style are not compared in version 1.
- One empty paragraph at the very end of the body is dropped. A document's final paragraph mark cannot be deleted, so accepting the deletion of the last paragraphs legitimately leaves one.
- Of `mc:AlternateContent`, only the chosen branch is read; `mc:Fallback` is skipped.

The **text view** keeps only each paragraph's path and text. It is the LibreOffice comparison.

## LibreOffice: limits and eligibility

LibreOffice is an independent established engine, but it does not represent everything a redline can carry. On 25.8.7.3:

- it recomputes `PAGEREF` results on import and ignores revisions inside a field result;
- it has no tracked bookmark changes, so a bookmark-only redline holds no revision it can see;
- it re-encodes fields and tables of contents, unwraps custom XML, rewrites content controls and regenerates paragraph ids, so field characters, markers, paragraph ids and style ids are judged only by the benchmark's engine and the `redline`-scope assertions;
- accepting the deletion of a document's last paragraphs leaves an empty final paragraph (handled by the view, above).

A LibreOffice comparison applies to a case only where the case declares it eligible. The authored redline is run through LibreOffice in the same session as the candidate. It must show LibreOffice seeing its revisions (`redlinesBefore` above zero when it has any), resolving all of them (`redlinesAfter` zero), and reproducing the expected text view. That calibration must match the declaration in both directions; any disagreement makes the case unmeasured rather than passed. A session that fails on a benchmark fixture is repeated once from a fresh profile before the case is left unmeasured. A candidate output LibreOffice cannot load, or whose revisions it leaves unresolved, fails the comparison.

Bookmarks have no tracked-change form in Word or LibreOffice. A redline can still mark a bookmark as inserted or deleted with `w:ins`/`w:del` around its markers, which the schema allows; whether bookmark changes round-trip is judged by the benchmark's engine alone. A declared-ineligible comparison is reported as not applicable with its reason. In `redline-v1`, 19 of 70 LibreOffice comparisons are declared ineligible: the field-result and bookmark-only cases for the reasons above, and the cases whose wrapper the comparison replaces whole with comments inside, because LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed.

## Suite score and comparisons

Cases belong to one category: `fields`, `comments`, `bookmarks`, `styles`, `revisions`, `consolidate` or `identity`. The suite score is the mean of the category means, published only when every case is measured. The report also gives the pass rate, passes by kind, and how many LibreOffice comparisons applied.

`bench redline compare BEFORE AFTER` refuses results with a different metric, suite digest, environment (LibreOffice and its Python, harness file digests, validator build) or adapter, but accepts different candidate commits. Both results must be complete runs of the same suite; a `--case` run is a diagnostic and is never complete. It lists each case that scored 100 before and does not now.

## Calibration

`--adapter authored` returns each case's authored redline. It must score 100 on every case with every check applicable to it, which shows that the declared expectations, the engine and the eligibility table are mutually consistent. CI runs it before the candidate. The tests also check that copying either input, a doubled field character, a duplicated style id, out-of-range or duplicated paragraph ids, and a whole-document delete-and-reinsert all fail.

## Run

```sh
python3 -m bench redline validate
python3 -m bench redline build-validator --out /path/to/validator
python3 -m bench redline build-docxodus --source /path/to/Docxodus --commit FULL_COMMIT_SHA --out /path/to/adapter
python3 -m bench redline run --adapter authored --candidate authored-calibration --validator /path/to/validator --out runs/redline-calibration
python3 -m bench redline run --adapter docxodus --candidate FULL_COMMIT_SHA --build /path/to/adapter --validator /path/to/validator --out runs/redline
```

`build-docxodus` requires a clean checkout at the exact commit. It compiles `adapters/docxodus-redline` against that checkout's `Docxodus/Docxodus.csproj` into the output directory and records the commit, tree, adapter source digests, build recipe digest, .NET SDK version and every built assembly's digest in `redline-build.json`. Each case re-verifies that record and the checkout before invoking the adapter. The adapter calls `DocxCompare.Compare`, `DocxCompare.Consolidate` or `RevisionProcessor.RejectRevisions`, with the author `Bench` and the fixed date `2026-01-01T00:00:00Z` so outputs are reproducible.

LibreOffice is found through `BENCH_LIBREOFFICE` or `PATH`; the UNO driver runs under `BENCH_LIBREOFFICE_PYTHON`, or the `python` LibreOffice ships beside `soffice`, or `/usr/bin/python3`. Their versions and digests are recorded with the run.

The #1190 cases cover bookmarks directly under tables and rows, plus plain-text paragraph controls, for comparison
and consolidation. The semantic view retains table/row marker order alongside cell contents; moving a
marker to a different row/cell boundary changes that view. The original 37 inputs are byte-identical.

The #1195 one-sided-wrapper authored redlines calibrate structurally and against the SDK, but LibreOffice retains both revision-scoped comments and an empty paragraph after accept/reject. The #1196 reviewer-added comment calibrates under LibreOffice accept; LibreOffice reject retains the comment. Those specific views are declared ineligible for LibreOffice checks; independent marker/definition and per-reviewer accept/reject checks remain mandatory.

The #1197 source reproducers intentionally contain two references to one comment; expected documents
contain one reference. Controls replace the same wrappers with valid single references. The authored
redlines carry one comment per view. LibreOffice retains both comments and an empty paragraph in each
resolved view (including the controls), so those accept/reject checks are declared ineligible after
capturing the discrepancy. Independent marker, definition and schema checks remain mandatory.

The #1210 cases distinguish package-local comment IDs from definition identity: an old note retained under a new ID, a replaced note, independent reviewer additions with different or identical text, and distinct-ID controls. Exact accepted/rejected anchors and definitions remain mandatory.


The #1206 consolidation cases combine a field-result edit, a prefix deletion or an added bookmark with a second reviewer’s tail edit; an ordinary-text pair is the control. All field characters and cached results are checked structurally after accept/reject, and all eight LibreOffice revision comparisons apply. PDF references recalculate body PAGE fields to 1 while the renderer intentionally retains cached body results, including the accepted 7; the two affected final PDF views retain their failing token checks rather than hiding this difference. A locked-field probe also recalculates in LibreOffice 25.8.7.3.

The #1211 body pair checks a removed comment reference in an edited paragraph and an unchanged-paragraph control. LibreOffice retains the comment after accepting the edited case and sees no revisions in the marker-only control; those three comparisons are declared ineligible from authored calibration. Independent markup and schema checks remain mandatory.

The #1212 note-insertion pair checks reference-to-definition identity in all resolved reviewer views. Authored redlines use sequential IDs in body order: LibreOffice misloads the valid nonsequential ordering. The prefix case leaves an empty first paragraph on LibreOffice reject, so only that comparison is ineligible; the suffix control and other comparisons calibrate. Full markup and schema checks remain mandatory.

The #1312 cases add a threaded reply to an unchanged comment. In the reproducers the original gives that comment no paragraph id and no commentsExtended part, or a different paragraph id from the revision's; the control gives it the same paragraph id in both. A correct redline keeps the original's comment and re-points the reply at that comment's own paragraph id (the authored redlines keep the revision's id where the original has none). `comment-threads` checks the link; LibreOffice exposes no revision for a reply whose markers are the only change and keeps the reply on reject, so all six of its comparisons are declared ineligible. LibreOffice renders of the Docxodus redlines before and after the fix are in [`docs/results/comment-reply-parent/`](results/comment-reply-parent/).

## Semantic preflight at raw limits

An identity comparison may declare `semanticPreflight` v1 with `limits: "raw-boundaries"` and
`changeCount: 0`. Both input digests must match. The source-bound adapter derives the maximum
entry/XML size, aggregate uncompressed size and compression ratio directly from that input's
ZIP directory, then calls the public byte-based `SemanticDiff.Compare` both with and without
the package supplement. It reports both observed counts before producing the ordinary redline.
A missing count, a non-integer count or a nonzero count fails the case. An exception scores zero.
The existing round trips, full semantic views, declared assertions and schema checks also apply.
The authored calibration establishes the identity through independently authored expected
documents; it does not claim to execute a candidate's semantic API. Metric contract version 2
records this extra mandatory check.

`redline-semantic-raw-limits-strict` and `redline-semantic-raw-limits-transitional-control`
contain the same original Marsh station agreement in different OOXML conformance classes.
Their expected documents and authored redlines are Transitional. The Strict reproducer fails
on Docxodus main before #1355; the control passes. See the labelled screenshots and capture
record under `docs/results/strict-semantic-limits/`.

## Session column widths

The `table-widths` operation opens one original package through the public `DocxSession` API,
changes its first table's column widths, records `ListRevisions().Count` and saves the result.
The versioned `tableWidths` declaration supplies the positive twip widths and tracking mode;
`revisionRegistry` requires one entry for tracked edits and zero for untracked controls. Missing,
wrongly typed or incorrect counts fail the case. Authored calibration uses its declared count,
not a claim to have executed the candidate API. Metric contract version 3 records this requirement.

The `table-widths` assertion v1 checks exact grid, cell and table widths in the accepted and
rejected views, including `dxa` types. The general text view intentionally ignores these
formatting properties, so it cannot replace these assertions. A width-only mutant still passes
the text view and fails the new assertions. Independent property resolution and schema checks
remain mandatory.

The four `redline-table-column-widths-*` cases start with two rows and columns of 2400/3200
twips. The full edit changes both columns to 2600/3000; the partial edit keeps 2400 and changes
only the second column to 3000. Each has an untracked control. Tracked reject restores the
original widths; either resolution of the revision-free control keeps the new widths.

LibreOffice 25.8.7.3 exposes zero revisions for both schema-valid authored property-only
redlines, for accept and reject alike. Those four text comparisons are explicitly ineligible;
the four control comparisons remain eligible. The harness recalibrates and fails as unmeasured
if the observed eligibility ever differs. This follows the existing policy used for other
revision kinds LibreOffice cannot expose. The exact width, registry and schema checks remain
mandatory. Labelled page rasters and diagnostic source-bound results are under
`docs/results/column-width-revisions/`; these are focused runs, not a full-suite score.

## Column edits across pending formatting

The `column-edit` operation calls the public untracked `InsertTableColumn` or `DeleteTableColumn`,
then the declared public bulk or selective revision resolver. It writes the resolved document.
Its `columnEdit` declaration v1 names the action, before/after position, physical cell index and
resolution (`reject-all`, `reject-each`, or `accept-all`). The observed public registry count
must be the declared integer zero, and independent markup inspection also requires no revisions.

The `table-state` assertion v1 independently checks exact grid widths and every row's leading
and trailing omissions, height, cell spans, preferred widths/types and shading. Declared rows
must fill the declared grid. The general text view omits these properties; deliberately changed
widths, spans, omissions, shading or height can preserve its text and must fail this assertion.
Metric contract version 4 records the new resolved-output operation and mandatory checks.

The twenty `redline-pending-grid-*` cases pair each pending-history reproducer with a
revision-free control. Real and no-op old grids cover insertion and deletion. Merged-cell
cases retain an older shading baseline; omitted-column cases retain older row height; two
edge insertions clone a merged reference into a new unit cell. Exact expected documents
retain the permanent structural edit while resolving only the earlier formatting. Every
expected output and authored calibration is original OOXML written independently of a
candidate. Calibration does not claim to execute the candidate API.

These resolved outputs contain no revisions, so LibreOffice compares their loaded text directly
against the authored calibration and expected output. Earlier declarations for property-only
redlines are unchanged. The page rasters under `docs/results/pending-grid-columns/` are local
diagnostics accompanying source-bound focused runs, not a full-suite score.

## Refusing block insertion beside cells

The `block-insert` operation calls the public session insertion API for a paragraph, horizontal
rule or one-cell table. Its `blockInsert` declaration v1 names the operation, the first body
anchor's kind (`p` or `tc`), before/after position and paragraph markdown. It saves the output
before probing public undo availability. The mandatory `editOutcome` declares exact, typed
success, error code, version delta and undo availability. Metric contract version 5 records
this operation and observation; missing values and boolean/integer substitutions fail.

Three original reproducer/control pairs cover cell anchors that cannot have block siblings
and valid body-paragraph anchors. Refusal requires `AnchorWrongKind`, version delta zero, no
undo entry, unchanged exact table geometry, zero revisions and matching document content.
Controls require success, version delta one and an undo entry. The table control includes
the API's documented separating paragraph between adjacent tables. The native adapter also
leaves every source file untouched, checked by the existing package digest guards.

Authored calibration validates independent expected packages and assertions; it does not
claim to execute the candidate API. All six LibreOffice loaded-text comparisons apply.
The labelled before/after page rasters and source-bound focused results are under
`docs/results/block-insertion/`. LibreOffice may repair invalid input when displaying it;
the schema and native outcome checks remain mandatory. These diagnostics do not report a
full-suite score or a Word reference. All prior DOCX bytes and eligibility declarations remain
unchanged; the PDF suite stays `core-v58`.
