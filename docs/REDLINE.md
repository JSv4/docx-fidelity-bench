# Redline track scoring

The redline track measures document comparison, not rendering. A candidate receives authored inputs and returns one package: a redline for a two-way comparison (`compare`) or an N-way consolidation (`consolidate`), or a resolved document for a revision operation (`reject`, `accept`). The benchmark then asks one question of that package: do its tracked changes reproduce the declared documents exactly, and is the package sound?

The suite is `redline-v56`, in `fixtures/redline/manifest.json`. It is separate from the PDF suite and has its own version, digest and results. Like the PDF track it is report-only: CI records the measurement but gates nothing.

## Cases

`bench/redline_fixtures.py` authors every package from literal text and original OOXML. Regenerating it must reproduce every file byte for byte; `python3 -m bench.audit` and the tests check this. Each case records:

- `operation` and its `inputs`, each with a path, SHA-256 and role (`left`/`right`, `base`/`reviewer`, or the tracked `input`);
- `expected`: for `compare` and `consolidate`, the document accept-all must produce (`accepted`: the revised document, or for consolidation the authored merge of every reviewer's change) and the document reject-all must produce (`rejected`: the original or base); for `reject` and `accept`, the `output` the operation must produce;
- `authored`: a redline (or resolved output) that is correct by construction, used for calibration;
- optional `reviewerExpected`: independently authored documents, with paths and SHA-256 digests, for every consolidation reviewer when conflict resolution or consensus attribution makes a selective result differ from an input; all selective comparisons remain mandatory;
- `assertions`: declared, versioned structural checks;
- `libreoffice`: for each expected document, whether LibreOffice can make that comparison (see below), with the reason when it cannot;
- `kind` (`reproducer`, `control` or `identity`), the Docxodus issue it pins, the rights record and the generator identity.

Every reproducer has a control: the same document shape without the trigger. Controls show that a failure belongs to the reported defect, not to the shape. Two identity cases calibrate the pipeline: a byte-identical pair, and a pair with equal content serialized with different run splits and revision-save ids, on which a comparison must report no change.

## Checks

A case scores **100** when every applicable check passes and **0** otherwise. There is no partial credit: a redline that is wrong on accept or reject is wrong. The evidence keeps a similarity ratio and a short diff for each failed comparison as diagnostics only.

1. **Conversion and integrity.** The candidate returns status `ok` with the output's digest. Its inputs are unchanged. The output opens as a package with one main document. The case's expected documents and authored redline are re-verified against the manifest digests when the case is scored. A known candidate failure (`failed`) scores zero; an unverifiable build or environment (`unmeasured`) blocks the suite score.
2. **Round trip through the benchmark's revision engine.** `bench/revisions.py` accepts every revision of the candidate's package and compares the result with `expected.accepted`, then rejects every revision and compares with `expected.rejected`. For `reject` and `accept` cases, the candidate's output itself is compared with `expected.output`. This engine is written for this repository and shares no code with any candidate. It applies ECMA-376 Part 1 §17.13.5 markup directly:
   - accepting keeps `w:ins` and `w:moveTo` content and drops `w:del` and `w:moveFrom` content; rejecting does the reverse, restoring deleted text and field instructions;
   - a removed paragraph mark joins its paragraph to the next paragraph of the same container, whose properties the joined paragraph keeps; a removed mark with no following paragraph keeps its paragraph unless the paragraph is empty and not the last of the body or the only paragraph of a cell, note, comment or header;
   - row markers (`w:trPr/w:ins|del`), cell markers (`w:cellIns`/`w:cellDel`) and revision markers in a math run's properties are resolved; move range markers are dropped;
   - a math object follows the marks on its control character (`m:*Pr/m:ctrlPr/w:ins|del`, and the `w:del` nested in a `w:ins` for a character inserted and later deleted): a removing mark takes the whole object and its text, whatever marks that text carries, as Word 2024 does;
   - custom-XML insertion, deletion and move ranges resolve the enclosing tags independently of their content. One enclosing range or two ranges crossing the opening and closing tags can remove an envelope; untracked content and unrelated empty inline envelopes survive. Partial removal of only one tag is reported as unsupported rather than treated as a successful resolution (see [custom-XML range semantics](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.customxmlinsrangestart));
   - property-change records (`w:rPrChange`, `w:pPrChange`, `w:sectPrChange`, `w:tblPrChange`, `w:trPrChange`, `w:tcPrChange`, `w:tblGridChange`, `w:tblPrExChange`, `w:numberingChange`) are dropped on accept and restore the prior properties on reject;
   - a block content control or custom-XML element left with no content is removed, as is a table left with no rows, and a hyperlink that had content before resolution and has none after it (a hyperlink has no tracked-change form of its own, so rejecting an inserted link leaves an empty `w:hyperlink`). A hyperlink the source wrote empty is kept.
   - For `consolidate`, attribution is checked too: accepting only one reviewer's revisions (by `w:author`) and rejecting every other revision must reproduce that reviewer's document, or the explicitly declared `reviewerExpected` projection. The bookmark-name cases declare the default base-wins policy: competing new ranges are absent, independent text edits survive, and a consensus range is credited to the first reviewer. These expectations are authored independently of candidate output and included in digest and regeneration audits.
3. **Round trip through LibreOffice.** `bench/lo_revisions.py` runs LibreOffice's own accept-all and reject-all (`.uno:AcceptAllTrackedChanges`, `.uno:RejectAllTrackedChanges`) through headless UNO, in a private profile and process, and saves the result with LibreOffice's Word filter. The expected document takes the same path, loaded and saved without an operation, so LibreOffice's import and export normalization applies equally to both sides. The two are compared on the text view. CI pins LibreOffice 25.8.7.3.
4. **Validity.** The pinned Open XML SDK validator (`tools/ooxml-validator`, DocumentFormat.OpenXml 3.5.1, file format `Microsoft365`) checks the candidate's package and every input. A finding counts by its error id, part and description; the package fails when any finding occurs more often than in every input. A package the SDK cannot open reports one `Package_Open` finding with the exception's description and no schema findings, so an output's `Package_Open` finding always fails, even when every input has the same one: otherwise an output keeping an input's open-time defect would never be validated. Conversely, an input the SDK cannot open reports no schema findings, so it licenses none of the output's: a repaired output is held to the full schema. The validator reads each package into memory before opening it, because the SDK, opening a file whose relationship target `System.Uri` rejects, writes its rewrite of that target back into the file even when opened read-only; the harness also gives the validator only temporary copies, so no validator can rewrite a fixture or an output, and refuses a run that changes a copy. An XPath alone never distinguishes findings, so a moved error is not new and a duplicated one is. A run without the validator has no suite score.
5. **Declared assertions**, each versioned:
   - `untracked-text` v1 (scope `redline`): each listed text occurs in a paragraph of the declared `story` (`body`, or `headers` for every referenced header and footer) outside every `w:ins`, `w:del`, `w:moveFrom` and `w:moveTo`. A tracked span breaks the paragraph's untracked text, so text cannot be assembled across it, and text placed in a part the view does not read (an unreferenced comment, note or header) does not count. Cases list only text a correct redline leaves unchanged, so deleting and reinserting a whole document, which would otherwise pass both round trips, fails;
   - `paragraph-count` v1: the number of `w:p` in the body of the raw redline (scope `redline`). This is a minimality requirement, not reversibility: the #1183 cases use it to require that the revised document's paragraph folds into the deleted one, as Word's compare does;
   - `para-ids-valid` v1: every `w14:paraId` in every XML part is eight hexadecimal digits, below `0x80000000`, and unique across the package;
   - `style-ids-unique` v1: no two `w:style` elements share a `w:styleId`, whatever their types;
   - `style-run-history` v1 (scope `redline`): every paragraph style whose `w:pPr` holds a `w:pPrChange` also has a `w:rPr` holding a `w:rPrChange`. Word 2024's Reject All restores a style from both markers and resets the run properties of a style without the second to its built-ins, so a spacing-only style revision rejects with 10 pt text; neither round trip sees this. The check is one-directional, because a run-only style revision was not measured. Metric contract 23 records this check;
   - `picture-bullets` v1 (scope `accepted` or `rejected`): the body paragraphs with text that are list items, in order, each with the SHA-256 of the image its level draws as a bullet (or none), equal the declared `items`. A level names its picture through `w:lvlPicBulletId`, a `w:numPicBullet` of that id in the numbering part and an image relationship of that part; a level override of the list instance is read before the definition. A missing bullet or image is reported as `unresolved` and fails. Neither round trip reads the numbering part, and the SDK validator accepts a level naming a bullet that does not exist, which Word 2024 refuses to open. Metric contract 31 records this check;
   - `comment-threads` v1 (scope `redline`): in the comments and commentsExtended parts, every entry is keyed to a comment's last-paragraph `w14:paraId`, every `w15:paraIdParent` names the last-paragraph `w14:paraId` of a comment that has its own entry, and for each declared `[reply, parent]` pair exactly one comment holds the reply's text and its entry names the comment holding the parent's text. Comment threading is not part of the semantic view, so neither round trip sees a reply detached from its parent;
   - `hyperlink-targets` v1 (scope `redline`): every `w:hyperlink` in the main document with an `r:id` resolves to exactly one relationship of the main part, of the hyperlink type with `TargetMode="External"`, and the set of their `Target` values equals the declared `targets`, compared as written after XML parsing, with no URI normalization. The semantic view records only a hyperlink's boundaries, so neither round trip sees a target rewritten (for example to the SDK's `rewritten://` placeholder), trimmed or dropped, or a link left on a relationship id another relationship also holds;
   - `relationship-ids` v1 (scope `redline`): every attribute in the relationships namespace (`r:id`, `r:embed`, …), in every XML part of the redline, names a relationship of that same part that is external or whose target is in the package; Strict names are read as Transitional. The semantic view does not follow a drawing into the parts it names and the SDK validator reports nothing for an id that names no relationship, so neither round trip nor validity sees a chart copied without its own relationships, which Word 2024 refuses to open. Metric contract 29 records this check;
   - `revision-count` v1: at most `max` revision records in the redline or output (scope `redline` or `output`); a `w:delText` or `w:delInstrText` outside any deletion also counts. Every `reject` and `accept` case requires zero.
   - `deleted-text-owned` v1 (scope `redline`): every `w:delText` and `w:delInstrText` in the raw redline lies in a `w:del` or `w:moveFrom` of its own story. A text box (`w:txbxContent`) is a story of its own, so a deletion around the run that anchors the box does not count for the text inside it. Word 2024 reports a package that breaks this as corrupt, while both round trips and the schema pass it. Metric contract 30 records this check.
   - `revision-text` v1 (scope `redline`): the declared body text occurs in a named move-source range as `w:t`, or in adjacent ordinary deletion wrappers as `w:delText`. It forbids deletion-only carriers in move sources and ordinary carriers in deletions. Metric contract version 12 records this check, which catches #1420 even when accept/reject and schema checks pass.

   - `mark-formatting` v1 (scope `accepted` or `rejected`): every body paragraph's mark (`w:pPr/w:rPr`), in document order, as the declared run `properties` it applies, read as `run-formatting` reads a run; the mark's revision markers are not properties, the number of paragraphs must match (an extra empty paragraph fails), text boxes are their own stories, and `mc:Fallback` is skipped. Neither round trip reads paragraph marks, so a redline that leaves a mark change untracked rejects to the revised mark unnoticed (Docxodus #1794). Metric contract 34 records this check.
   - `run-formatting` v1 (scope `accepted` or `rejected`): the resolved body's text as spans of consecutive characters carrying the same values of the declared run `properties`, whatever the run boundaries. Each span is the text and its sorted entries: a toggle's name when it is on, or `name=value` for any other property applied (a neutral value such as an underline of `none` is not applied); undeclared run properties are ignored. Text is `w:t` and restored `w:delText`, a symbol's character, and a tab, break or special hyphen as its character; text boxes are their own stories and an `mc:Fallback` is not read. Only supported properties may be declared: toggles, read as on or off, and properties read by their `w:val`. Neither round trip reads character formatting, so a redline that archives a run's original formatting on the wrong run rejects to the right text with the wrong words formatted (Docxodus #1784). Metric contract 33 records this check.
   - `section-change-values` v1 (scope `redline`, `accepted` or `rejected`): one entry per physical section of the raw redline or of the independently resolved endpoint, in body order (the property history in `w:sectPrChange` and text boxes excluded), maps each declared property to its literal value in the section and in the `w:sectPr` its `w:sectPrChange` archives: `name@attribute` reads the attribute as written, `name` reads a toggle as `on` or `off` (a missing `w:val` is on), and a value either side leaves out, or an archive the section lacks, is null. The number of sections must match. Docxodus #1775 reports, from a desktop word processor this bench has not captured, that it reads a value left out of one side of a section change as unchanged, not as its default: it rejects a portrait-to-landscape change whose archive leaves `w:orient` out to landscape, and does not see a final section's title page turned off by leaving `w:titlePg` out (an inline section break is read correctly). Neither round trip reads section properties. Metric contract 32 records this check.
   - `section-boundaries` v1 (scope `accepted` or `rejected`): inline section breaks must occur after exactly the declared zero-based body paragraph indices in `afterParagraphs`. Paragraphs are enumerated in XML document order beneath the body, including nested containers; the trailing body section properties are excluded. This binds section and running-story changes to their carrier paragraphs even when the semantic view and section-story order match. Metric contract version 18 records this check.
   - `inline-trees` v1 (scope `accepted` or `rejected`): the complete ordered `m:oMath`, `w:drawing`, or `w:pict` subtrees in the resolved body match declared XML. It retains operators, properties, geometry and textbox content; image references resolve to the SHA-256 of their actual package bytes. Only engine addressing attributes and remappable `wp:docPr/@id` values are ignored. Surviving deleted text carriers normalize to ordinary text, empty run properties are discarded, and adjacent plain text runs with identical attributes and properties coalesce. Metric contract version 14 additionally includes VML pict carriers.

`inline-trees` v2 adds `story: "headers"` for ordered native subtrees across referenced headers and footers in the independently resolved document. Repeated references to the same part are counted once; image ids resolve against each owning part. Text nodes honor inherited `xml:space` and then coalesce equivalent run splits; significant spaces still compare exactly. This extends the body-only v1 assertion without changing existing cases. Metric contract 20 records the running-story check.

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

`build-docxodus` requires a clean checkout at the exact commit. It compiles `adapters/docxodus-redline` against that checkout's `Docxodus/Docxodus.csproj` into the output directory and records the commit, tree, adapter source digests, build recipe digest, .NET SDK version and every built assembly's digest in `redline-build.json`. Each case re-verifies that record and the checkout before invoking the adapter. The adapter calls `DocxCompare.Compare`, `DocxCompare.Consolidate` or `RevisionProcessor.RejectRevisions` (`accept`: `RevisionProcessor.AcceptRevisions`), with the author `Bench` and the fixed date `2026-01-01T00:00:00Z` so outputs are reproducible.

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

## Text edits within mixed runs

The `replace-span` operation calls public `DocxSession.ReplaceTextAtSpan` on one input, with
its `spanEdit` v1 declaration specifying tracking, physical body-paragraph index, start,
positive length and replacement. It returns the saved package. Like comparison and table-width
operations, the harness resolves that output independently through its markup engine and
LibreOffice, comparing both accepted and rejected views with authored expectations. A public
API refusal is a failed conversion. Metric contract version 6 records the new operation.

Sixteen original cases pair each mixed-run reproducer with a nearby control whose marker
follows all edited text. Tabs and line breaks cover both direct and tracked editing, with
selections before and across each marker. Direct single-letter replacements and tracked
single-letter deletions preserve its position; cross-marker replacements begin at the first
selected text node. Tracked rejection restores the original text on both sides of the marker.
Direct edits are permanent, so both resolved views match the revised document.

All expected packages and calibration redlines are independently written here. Their inline
views include tab/break tokens, so an output with the right letters and a displaced marker
fails. Paragraph-count assertions also require three paragraphs in each resolved view. The
markup resolver produces internal view trees and may retain restored `delText` node names;
these are not serialized candidate packages or a claim about residual native revisions.

The labelled sheets under `docs/results/mixed-run-edits/` show actual candidate packages after
LibreOffice rejects their revisions, then renders them as PDF. A direct-edit case has no revisions
to reject. Hashes, exact source identities and focused run contracts are recorded alongside them.
These diagnostics do not claim a full-suite score or a Word reference. All previous DOCX bytes
and LibreOffice eligibility declarations remain unchanged; the PDF suite stays `core-v58`.

## Reviewing a tracked column across omitted and merged rows

`column-edit` declaration v2 extends v1 with a required `tracked` boolean and supports insertion
followed by the existing bulk/selective resolution choices. Version 1 inputs and measurements
retain their untracked behavior. The v2 adapter records the public registry before resolution,
attempts the declared native resolver, then saves its actual result even if resolution fails.
This exposes the failed workflow without substituting an expected document.

A mandatory `columnReview` declaration v1 requires the exact integer `beforeCount` (one tracked,
zero direct), boolean `supported` true for every listed revision, and boolean `resolutionSuccess`
true. Missing or mistyped observations fail. The existing final registry assertion requires
integer zero, while independent markup requires no revisions and exact table-state checks cover
grid widths, row omissions, cell spans, widths/types and fill. Metric contract version 7 records
the new observation. Authored calibration validates the independently authored packages and
assertions; it does not claim to execute a candidate API or measure its registry.

Eight original cases cover a leading omission with bulk reject, a trailing omission with bulk
accept, and a table combining a widened merged row and an omitted row with selective reject or
bulk accept. Each has a direct-edit control; its structural edit remains permanent when reject
is requested. Nonuniform grid widths make the expected column and widened cell explicit.
All eight LibreOffice loaded-text comparisons apply. Prior eligibility declarations are unchanged.

The labelled sheets under `docs/results/tracked-column-gaps/` render actual candidates after the
native review attempt. A failed attempt can leave unresolved markup, so the captions state its
native outcome and before/after registry counts. LibreOffice exports that saved package as PDF;
it is not performing the native review. Hashes, exact sources and focused run contracts are
recorded alongside the sheets. These diagnostics do not claim a full-suite score or Word reference.
All previous DOCX bytes are unchanged and the PDF suite remains `core-v58`.

### Reviewer accounts and namesakes (Docxodus #1317)

`redline-v17` adds seven original Summit cases: another account with the same display name,
that name already used without an account, AD principal-name and object-id aliases under a
different name, the legacy name-only control, and a free name's first tracked edit or comment.
The PDF suite is unchanged at `core-v62`. All earlier DOCX bytes remain unchanged.

The `revision-ownership` operation takes one source and a version-1 `revisionOwnership`
declaration: reviewer `author`, nullable `identities` (`providerId`/`userId` records),
`configure` (`open` or `operation`), `action` (`delete-block`, `replace-text` or `add-comment`),
zero-based `paragraphIndex`, literal `text` and nullable `queryAuthor`. A non-null query author
requires version-1 `authorNameStatus` expectations for `before` and `after`, each `free`, `own`
or `taken`. The adapter must return the actual public query envelopes for both checkpoints.
The legacy control opts out of accounts and of the new query, so it remains executable on an
older candidate.

Metric contract version 8 adds `people-identity` and `pending-insertion-deletion` assertions,
both version 1 and scoped to the raw redline. The first follows the main part's people
relationship and checks every account recorded for the declared name exactly, including
absence, duplicates and ambiguous presence records. The second requires exactly one matching
tracked deletion, with the declared author and text, inside the original author's insertion.
All ordinary paragraph, untracked text, schema and independent accept/reject checks still apply.

Both accepting and rejecting **all** revisions remove an originally pending inserted paragraph
that has subsequently been deleted. These round trips alone cannot prove that the counterparty's
proposal survived as reviewable markup. The retained-insertion assertion is therefore mandatory
on the two foreign-name cases; a negative test demonstrates that erasing the paragraph can pass
both round trips while failing that assertion. The people assertion independently detects a
missing identity claim even though semantic view version 1 does not include reviewer metadata.

The native adapter uses public reflection only to bind the new account DTO, setting and methods,
so the same adapter compiles against pre-feature candidates. Missing requested account support
is an operation failure (measured score zero), rather than a build failure or emulation by name.
No Word behavior is inferred from these explicit feature contracts. Screenshots are review
evidence; only recorded independent round-trip and schema measurements support redline scores.


## Move range membership

The six #1340 reject cases distinguish moved wrappers from their named range containers. Plain
`XY` after or between moved wrappers survives, as does text between two same-named disjoint
destination ranges, including a range spanning paragraphs. The unsplit move and text outside the
range are controls. Expected paragraph lists were independently observed using native Word for the
web accept/reject on 2026-10-24; the core repository pins the exact original source bytes and endpoint
hashes in `TestFiles/RP/MoveRangeMembership/word-endpoints.json`. These benchmark packages are
new literal OOXML with the benchmark's own styles and section defaults, so their source bytes differ;
no native Word PDF is registered as a scoring reference here. The existing corpus is byte-identical.

The benchmark invokes stateless rejection. The core tests also require the session registry to list
disjoint same-named ranges as one supported move and check bulk/selective acceptance and rejection
against Word. This track does not score session enumeration or selective resolution.

## Package shapes and external link targets (Docxodus #1384, #1388)

`redline-v18` adds eight original cases in a new `packages` category, which the suite score
weights like every other category. Each pair adds one unrelated paragraph to a document whose
package, not its text, is the trigger. The PDF suite moves to `core-v72` with four matching inputs.

The four #1388 cases hold an external hyperlink to `mailto:first@example.com;second@example.com`,
a multi-recipient target that `System.Uri` rejects ("Invalid URI: The hostname could not be
parsed"), and the same shapes with `mailto:solo@example.com` as controls. In one pair the link is
on both sides beside the added paragraph; in the other it is inserted with its paragraph, so the
original has no hyperlink relationship. `hyperlink-targets` requires the redline to keep the target
exactly as written: the Open XML SDK's own workaround for such targets substitutes a random
`rewritten://` address that both round trips would accept.

Metric contract version 9 records three changes: this assertion, the rule that an output which
fails to open always fails validity, and the markup engine's removal of a hyperlink that
resolution leaves empty (needed by the inserted-link pair, whose authored redline otherwise
leaves an empty `w:hyperlink` behind on reject).

The four #1384 cases share one shape: a font table that embeds a part, a glossary document and an
external hyperlink to `https://example.com/terms`. The control types the embedded part by a `ttf`
Default, gives the glossary its own Override and the hyperlink its own relationship id. Each
reproducer breaks exactly one of these, in a form the Open XML SDK refuses at open: the embedded
part has no content type, the glossary is typed only by the generic `application/xml` Default, or
the hyperlink relationship reuses the settings relationship's id. The expected documents are the
inputs themselves; the authored redlines write the control's well-formed package. The inputs'
`Package_Open` findings license nothing: a redline that keeps the input's defect fails validity. The embedded part holds the
placeholder bytes declared in `bench/common.py`, not a font program (see [RIGHTS.md](../RIGHTS.md)).
A variant with the embedded part absent from the zip is not in the corpus: LibreOffice refuses to
load it, so its comparisons could not be calibrated.

All sixteen LibreOffice comparisons apply. Authored calibration scores 100 on all eight. On
Docxodus 3e4335d8 the five reproducers score 0 and the three controls 100: four comparisons throw
(`Invalid URI: The hostname could not be parsed.`, the glossary content-type refusal and the
`rSettings` id conflict), and the untyped-font comparison returns a redline that drops the font
table's relationships, so the SDK cannot open it (`Package_Open`). On Docxodus main 3a29e133,
after [PR #1400](https://github.com/JSv4/Docxodus/pull/1400) (#1388) and
[PR #1401](https://github.com/JSv4/Docxodus/pull/1401) (#1384) merged, all eight score 100 with all
sixteen LibreOffice comparisons applied. Labelled before/after sheets and their capture record are under
[`docs/results/package-shapes/`](results/package-shapes/); these are focused diagnostics, not a
full-suite score.


## Visible run atoms and inline XML

`redline-v19` adds twenty original cases for Docxodus #1387/#1409. Each tracked span replacement selects one native atom (tab, line/carriage break, page/column break, positional tab, special hyphen or symbol), with an ordinary-text control. Another pair selects text in inline custom XML versus ordinary runs. Offsets follow the corrected visible-character contract; older engines that omit atoms fail the reproducer. These are public `replace-span` operations, not comparisons.

The optional `run-atoms` v1 assertion checks the ordered direct run children in the accepted/rejected body, including element spelling and every Word-namespace attribute. Tab-stop definitions do not count. It distinguishes `cr` from `br`, native elements from equivalent literal text, and exact positional-tab alignment/relative origin/leader, symbol font/code and break type/clear state. Existing complete semantic views, schema checks and all applicable LibreOffice comparisons stay mandatory. Metric contract version 10 records the assertion. This does not add a query, markdown-patch or editor observer.

Three newly authored views have narrow LibreOffice 25.8.7.3 qualifications, reproduced in separate fresh profiles before and after the candidate. Source, accepted, rejected and calibration packages for all three have actual zero SDK findings. Accepting the page/column-break calibration resolves its revisions but retains the deleted break and splits the paragraph; rejecting remains eligible. In the symbol case, LibreOffice imports the source's trailing `Birch` as five Symbol-font `w:sym` carriers, whereas authored rejection retains `w:t`; its text-only view omits those symbol tokens. Symbol acceptance remains eligible. All independent markup, exact-atom and schema checks remain mandatory on these cases. No existing eligibility is changed.

The [twenty labeled native previews](results/visible-atoms/README.md) are review artifacts, not Word references or PDF scores. Focused before/after measurements bind exact sources; a subset run has no full-suite headline score. Earlier numeric-offset cases remain unchanged and can expose intentional incompatibility with the new offset contract.

## Whole-paragraph control preservation

`redline-v20` adds fourteen original cases for Docxodus #1406. Eight use public untracked
`replace-text` to echo a paragraph or change text on both sides of a bound or citation control.
Six cover multiline strike/code/link controls and single-line controls, pinning hard-break marker
consumption inside these inline spans. Every reproducer has an ordinary-text control.
`paragraphRewrite` v1 declares an exact zero-based body
paragraph index and markdown payload. It calls `DocxSession.ReplaceText` directly, with no
candidate-specific repair or native XML write in the adapter.

`content-controls` v1 compares the complete ordered native control subtrees against authored XML
in each accepted/rejected view: element names, attributes, text, fields and nested markup.
Only Docxodus's addressing attributes in `http://powertools.codeplex.com/2011` are ignored;
serialization indentation and namespace prefixes carry no meaning. Binding paths/store ids and
citation instructions are mandatory even when visible text is unchanged. Zero revisions in the
raw candidate are mandatory for this untracked operation. Existing complete semantic, schema
and both LibreOffice checks remain required, with no new exclusions. Metric contract version 11
records this observer. These cases do not cover control fill APIs, query/patch observations,
tracked whole-paragraph edits or browser interaction.


## Atomic source content

`redline-v22` adds ten cases for Docxodus #1421: an equation after a tab, the same change consolidated with a second reviewer's independent suffix edit, discarded field-instruction text before an equation, an unfinished field capturing a hyperlink/tab, and a single drawing supplying image and textbox content. Each has a trigger-free control. The two consolidation cases require correct reviewer attribution as well as combined accept/reject results. Existing 198 cases remain unchanged.

The equation/drawing assertions inspect the native content that a text-only observer cannot distinguish. Negative examples change a summation operator, image bytes or textbox text; positive examples allow equivalent math run splits. Untracked-text assertions keep the unchanged suffix and closing paragraph outside revisions where the source can be safely split.

The authored LibreOffice 25.8.7.3 calibration has 15 unsupported views: 12 whole-equation resolutions retain both alternatives, unfinished-field rejection loses its tab, and two whole-drawing resolutions retain an extra empty paragraph. These declarations affect only the corresponding new cases; the other five views remain eligible. Independent complete semantic views, selective reviewer results, exact subtree assertions and SDK checks remain mandatory. [The ten labeled screenshots and source-bound measurements](results/atomic-source/README.md) record the observed limitations and the focused before/after results. No desktop Word behavior or complete suite score is inferred.


## Pure textbox geometry

`redline-v23` adds two original cases for Docxodus #1425. Two textboxes share one VML carrier. The reproducer changes only the first width from 80pt to 120pt; the control changes only its body text. Exact accepted/rejected `w:pict` assertions retain both shapes, all geometry attributes, and both bodies. Mutation tests reject a restored old width and missing textbox text, while input-copy checks include structural assertions when the text-only semantic views are equal.

Both authored whole-paragraph redlines retain an extra empty paragraph in LibreOffice 25.8.7.3 after acceptance or rejection. These four measured calibration limitations are declared ineligible; independent markup, exact geometry/body assertions, and SDK checks remain mandatory. [Focused results and labeled previews](results/textbox-geometry/README.md) disclose the limitation without inferring Word behavior or a full-suite score.


## Field defaults and paragraph spacing

`redline-v27` adds simple and complex unchanged PAGE fields beside two inserted paragraphs
and a literal-text control for Docxodus #1533. The defaults change after-spacing from 80
to 280 twips and automatic line spacing from 260 to 380. All three cases require exact
text/field round trips, schema validity, and effective paragraph spacing.

Metric contract 15 adds `paragraph-spacing` v1 for accepted/rejected views. It resolves
style property revisions independently, then overlays literal document defaults, the
default or named paragraph style's basedOn chain, and direct paragraph properties per
attribute. It checks every text-bearing top-level body paragraph, so a revision engine's
empty terminal paragraph does not change the count. Table conditional formatting, empty
paragraph layout, and automatic/line-based spacing are outside this assertion: extra
spacing attributes remain in the observed values and fail a four-axis literal declaration.
Semantic text and field checks still detect lost content. Mutation tests cover lost
formatting history, direct overrides, inheritance and unsupported spacing modes.


`redline-v28` adds four complete-rewrite cases for #1535: articles, literal ordinals,
linked articles, and a distinct-word control. Metric contract 16 adds `revision-blocks`
v1, which requires nonempty inserted and deleted text to form exactly two consecutive
runs in body paragraph order. A shared boundary paragraph is allowed, but alternating
inserted/deleted words within it fail. Endpoint equivalence and schema checks
remain mandatory; the assertion measures arrangement, not Word Compare parity.


`redline-v29` adds inserted opening sections with explicitly empty headers/footers and
a stable-section control. Metric contract 17 adds `section-stories` v1: in current
section order, it follows the declared running-story kind and inheritance, requiring
exact raw text including deleted text. A reference without `w:type` counts as the default
kind, and a section with two references of the declared kind observes no story, so it fails. Missing or wrong-kind relationships fail. Section
property history and textboxes do not create extra sections for this assertion.

For the two inserted-section reproductions, LibreOffice 25.8.7.3 cannot calibrate rejection:
it keeps the inserted empty section and extra paragraph/running-story bindings. That one
provider check is explicitly ineligible; acceptance, independent exact markup endpoints,
review-story assertions and SDK validity remain mandatory. The stable-section control
calibrates both LibreOffice resolutions.

### Alternate textbox search and edits

`redline-v31` adds four cases for Docxodus #1560: an exact-span edit and a unique visible-search
edit of a DrawingML/VML textbox, each paired with a VML-only control. `spanEdit` version 2 requires
exactly one public `Grep` match and edits it through `ReplaceMatch`; version 1 retains its numeric
paragraph/span contract. Both paths use tracked edits. Metric contract 19 includes the unique-query
requirement. Exact resolved drawing and VML trees check both compatibility representations,
including their text and geometry; independent round trips and SDK validation remain mandatory.
All 239 preceding cases and document bytes are unchanged.

Metric contract 21 adds `section-flags` assertions for exact first-page visibility in the review
and independently resolved endpoints. Section property history and nested textbox stories are
excluded from the physical section inventory; absent flags and explicit off values are false.
The Juniper #1555 fixtures also require exact per-section header/footer text and boundary carriers.

### Positional short rewrites

`redline-v34` applies the explicitly requested #1556 review policy to the four short
#1535 complete-rewrite cases: each whole old sentence stays beside its positional replacement.
Their inputs and accepted/rejected endpoints are byte-identical; only the authored review order
and arrangement assertion change. Four new long-rewrite controls retain `revision-blocks` v1.
Four independent Myrtle cases cover a two-paragraph rewrite, interior and unequal-count controls,
and identical-reviewer consensus. Consensus is credited once to the first reviewer, with exact
selective-reviewer endpoints. This is a review arrangement policy, not a Word Compare oracle.

Metric contract 22 adds `positional-rewrites` v1 (scope `redline`). Its nonempty `before` and
`after` arrays declare the complete ordered sentences. Every sentence must occur intact on its
revision side, each positional pair must share or occupy adjacent body paragraphs, and pair
ranges must be ordered without overlap. A paragraph permits at most two revision-side runs and
no untracked visible text. Wrong partners, whole-side blocks and word interleaving fail even if
accept/reject endpoints match. All existing round-trip, attribution and SDK checks remain
mandatory. `revision-blocks` v1 and historical evidence retain their original meaning.

### A revised document without `w:pPrDefault`

`redline-v40` adds two original Teasel cases for Docxodus #1652. The original declares 200/276
default paragraph spacing. The reproducer's revised document has `w:docDefaults` with no
`w:pPrDefault`, which Word 2024 lays out at `w:after="160" w:line="278"`; the control's revised
document states those values. Both must accept to 160/278 and reject to 200/276 under
`paragraph-spacing`, with `style-run-history` on the recorded style revision. See
[the evidence](results/missing-paragraph-default/README.md).

### Style revisions that Word rejects whole

`redline-v35` adds two original Quince cases for Docxodus #1576. Both change default paragraph
spacing from 200/276 to 0/240 beside a one-word edit. The reproducer declares the spacing in the
document defaults; the control declares it in the `Normal` style, so the style definitions
differ. Each authored redline records the spacing on `Normal` with both a `w:pPrChange` and a
`w:rPrChange`, as Word's own compare output does. Accept/reject round trips, exact
`paragraph-spacing` on both endpoints and the new `style-run-history` v1 check are mandatory. The
cases pin Word's Reject All behaviour, not its Compare output: for document-default differences
Word's Compare adopts the revised defaults untracked, which cannot reject to the original. See
[the evidence](results/default-spacing-history/README.md).

## Session revision resolution

The `revision-resolve` operation opens one package that already holds tracked changes through
the public `DocxSession` API, lists its revisions, runs the declared bulk resolver and saves the
result. The `revisionResolve` declaration v1 names the resolution (`accept-all` or `reject-all`).
The adapter saves the session's actual document even when resolution is refused, so a refusal is
measured and never replaced by an expected document.

A mandatory `resolutionReview` declaration v1 requires the exact positive integer `beforeCount`,
boolean `supported` true for every listed revision, and boolean `resolutionSuccess` true. Missing
or mistyped observations fail. The final registry count must be the integer zero, and independent
markup inspection also requires no revisions. Metric contract version 24 records the operation
and the observation. Authored calibration validates the independently authored packages and
assertions; it does not claim to execute a candidate API.

`table-state` v2 extends v1 for these cases. It reads a row's cells through cell-level content
controls (`w:tr/w:sdt/w:sdtContent/w:tc`) and adds a `control` entry to every cell: the `w:id` of
the control around it, or null. A control left holding no cell is reported as an entry without a
span, so it cannot match a declared state. Version 1 still reads only a row's direct cells, so
earlier declarations and measurements are unchanged. Version 3 (`redline-v57`) also reads a table's rows through table-level
content controls; see [Content-control rows and a removed section break](#content-control-rows-and-a-removed-section-break-docxodus-1804-1805).

### Cell revisions (Docxodus #1404)

`redline-v36` adds twelve original Orchard cases: a three-column fixed-layout table whose first
row carries one `w:cellDel` or `w:cellIns`, above an unrevised row.

| Reproducer | Mark | Resolution | Expected first row | Control |
| --- | --- | --- | --- | --- |
| `redline-cell-delete-first-accept` | deletion on the first cell | accept all | the second cell spans two columns and is 4800 wide | insertion on the first cell, accepted |
| `redline-cell-delete-first-reject` | the same | reject all | three cells | deletion on the middle cell, rejected |
| `redline-cell-delete-middle-accept` | deletion on the middle cell | accept all | the first cell spans two columns and is 4800 wide | insertion on the middle cell, accepted |
| `redline-cell-delete-wrapped-accept` | deletion on the middle cell; every cell in its own content control | accept all | the first cell spans two columns in its control and is 4800 wide; the deleted cell's control is gone | insertion on a bare middle cell, accepted |
| `redline-cell-delete-wrapped-reject` | the same | reject all | three cells, each in its control | deletion on a bare middle cell, rejected |
| `redline-cell-insert-wrapped-accept` | insertion on the middle cell; every cell in its own content control | accept all | three cells, each in its control | insertion on a bare middle cell, accepted |

The expected documents follow desktop Word 2024 (16.0.20326) Accept All and Reject All on
authored probes: a deleted cell gives its grid column and its `w:tcW` to the cell before it, or to
the cell after it when it starts the row, and a content control around the removed cell alone
leaves the row with it. Docxodus main before the fix lists the first-cell and wrapped
reproducers' revisions as unresolvable and refuses bulk resolution. It resolves the bare
middle-cell deletion but keeps the absorbing cell's old 2400 width, which the exact `table-state`
widths catch; that is why the accept controls mark an insertion, which keeps every cell.

Rejecting a tracked cell insertion is covered by the #1688 cases below.

All twelve LibreOffice loaded-text comparisons are declared eligible: the outputs hold no
revisions, so LibreOffice only loads the expected, authored and candidate documents the same way.
All previous DOCX bytes are unchanged.

### Cells that leave a row (Docxodus #1688)

`redline-v37` adds twenty original Orchard cases, ten reproducers each followed by a control, on
the same table as the #1404 cases. A cell leaves its row when its deletion is accepted or its
insertion is rejected; desktop Word 2024 (16.0.20326) resolves the two alike, and every expected
document here matches what Word wrote for the case's own source.

| Reproducer | Resolver | First-row marks, resolution | Expected | Control |
| --- | --- | --- | --- | --- |
| `redline-cell-insert-middle-reject` | session | insertion on the middle cell, reject all | the first cell spans two columns, 4800 wide | deletion on the middle cell, rejected |
| `redline-cell-insert-first-reject` | session | insertion on the first cell, reject all | the second cell spans two columns | the same insertion, accepted |
| `redline-cell-insert-wrapped-reject` | session | the same on a cell in its own content control | the first cell spans two columns in its control; the inserted cell's control is gone | the same insertion, accepted |
| `redline-cell-delete-row-accept` | session | deletion on all three cells, accept all | the row is removed | deletion on the first two cells, accepted |
| `redline-cell-insert-row-reject` | session | insertion on all three cells, reject all | the row is removed | insertion on the first two cells, accepted |
| `redline-cell-delete-row-shared-accept` | session | two reviewers' deletions covering the row, accept all | the row is removed | the two reviewers' deletions on the first two cells, accepted |
| `redline-cell-delete-only-row-accept` | session | deletion on every cell of a one-row table, accept all | the table is removed; the paragraphs stay | insertion on the middle cell of the one-row table, accepted |
| `redline-cell-processor-accept-first` | `RevisionProcessor` | deletion on the first cell, accept | the second cell spans two columns | deletion on the middle cell, accepted |
| `redline-cell-processor-accept-wrapped` | `RevisionProcessor` | deletion on a middle cell in its own content control, accept | the first cell spans two columns; the deleted cell's control is gone | the same deletion on a bare cell, accepted |
| `redline-cell-processor-reject-insert` | `RevisionProcessor` | insertion on the middle cell, reject | the first cell spans two columns | deletion on the middle cell, rejected |

The `RevisionProcessor` accept cases use a new `accept` operation, the counterpart of `reject`:
the candidate's whole-document acceptance of one tracked input is compared with an authored output.
Metric contract version 25 records it. The case with no table left declares no `table-state`; the
markup comparison with its table-free expected document carries that check, and a test shows that a
candidate which strips the marks and keeps the row, or the table, scores zero on it.

Before the fix Docxodus removed a rejected inserted cell without widening its neighbour, refused a
row whose every cell leaves, and in `RevisionProcessor` dropped a deleted first cell without widening
and left `w:cellDel` on a cell inside a content control.

One shape is deliberately absent because Docxodus differs from Word there by design: a rejected
insertion in a table where no row keeps every cell (a whole inserted column, a table of one row).
Word merges the leaving cell into its neighbour; Docxodus widens after a rejected insertion only
when a row that kept its cells shows the table to be wider, so that rejecting a comparison's
inserted cell in a row already short of the grid gives the original row back. All twenty
LibreOffice loaded-text comparisons are declared eligible. All previous DOCX bytes are unchanged.

The benchmark's own revision engine does not model cell-level content controls: accepting the
wrapped deletion it drops the whole row. It is not used to score these cases (they compare the
candidate's output with the authored one), and the authored-calibration test that replays `accept`
and `reject` inputs through it skips `redline-cell-processor-accept-wrapped` for that reason.

### A deleted cell whose paragraph mark is deleted (Docxodus #1694)

`redline-v38` adds eight original Orchard cases, four reproducers each followed by a control, on
the same table as the #1404 and #1688 cases. The first row's first or middle cell carries
`w:cellDel`, its run sits in `w:del`, and in the reproducers its paragraph mark is tracked as
deleted too (`w:pPr/w:rPr/w:del`). That is the markup a comparison writes for a cell the revised
document no longer has. Desktop Word 2024 (16.0.20326) accepts it by removing the cell and widening
nothing: the row keeps two cells of 2400 and stops one column short of the grid. With only the run
deleted, Word gives the column to a neighbour, as it does for a deleted cell with plain content.
Word resolved each case's own source to the same laid-out table as its expected document.

| Reproducer | Resolver | Deleted cell | Expected first row | Control (run deleted, mark not) |
| --- | --- | --- | --- | --- |
| `redline-cell-delete-struck-first-accept` | session | first | `Pear lot`, `Fig lot`, 2400 each | `Pear lot` spans two columns, 4800 wide |
| `redline-cell-delete-struck-middle-accept` | session | middle | `Plum lot`, `Fig lot`, 2400 each | `Plum lot` spans two columns, 4800 wide |
| `redline-cell-processor-accept-struck-first` | `RevisionProcessor` | first | `Pear lot`, `Fig lot`, 2400 each | `Pear lot` spans two columns, 4800 wide |
| `redline-cell-processor-accept-struck-middle` | `RevisionProcessor` | middle | `Plum lot`, `Fig lot`, 2400 each | `Plum lot` spans two columns, 4800 wide |

Before the fix both resolvers widened the neighbour in the reproducers as well, which the exact
`table-state` spans and widths catch. A `table-state` declaration may now describe a row that
covers fewer grid columns than the table grid, never more; metric contract version 26 records it.
How an output is compared with a declaration is unchanged.

A comparison of the two documents is not added as a case. The `compare` operation resolves the
candidate's redline with the benchmark's own engine, which removes a deleted cell without widening
in every case, and its view does not carry spans or widths, so it cannot see this defect; the
resolvers that had it are measured directly above. All eight LibreOffice loaded-text comparisons
are declared eligible. All previous DOCX bytes are unchanged.

## Math objects inserted and then deleted (Docxodus #1189)

`redline-v39` adds three original Juniper cases. A fraction's control character
(`m:fPr/m:ctrlPr`) carries `w:ins > w:del`, the only nesting `CT_MathCtrlIns` allows, with its
numerator and denominator inserted. Word 2024 removes the fraction on Accept All and on Reject
All. The reproducer accepts that document through the `accept` operation; the controls accept a
fraction that was only deleted and reject the nested form. Each output is compared whole with the
declared document and must hold no revisions. Expected documents are authored from Word's
endpoints.

Metric contract version 27 records a change to the benchmark's own engine, which now removes a
math object whose control character carries a removing mark. Before, it resolved only the text
inside, so an inserted-then-deleted object kept its inserted text on accept. No earlier case holds
a control-character mark, and all previous DOCX bytes are unchanged. Session listing and selective
resolution of the two revisions are covered by Docxodus's own tests, not scored here. See
[the evidence](results/math-control-revisions/README.md).

## Rejecting revisions in a Strict-conformance package (Docxodus #1268)

`redline-v41` adds an original pair. One paragraph deletes "Amber prism" and inserts "Indigo
prism"; the reproducer's input is an ISO/IEC 29500 Strict package and the control's is the same
package in the Transitional class. The two inputs differ only in the WordprocessingML namespace
and the relationship-type URIs, which the generator's existing `strict` option substitutes after
every part is built. Both use the `reject` operation: the output is compared whole with the
Transitional original and must hold no revisions. LibreOffice loads both inputs, and all its
comparisons apply.

Metric contract version 28 records a change to the benchmark's own engine, which now reads the
XML and relationship members of a Strict package under the Transitional WordprocessingML, math and
relationship names it matches. Before, it found no revision and no text in a Strict package, so it
could not resolve the Strict input in the authored calibration and would have scored a correct
Strict output as empty. A candidate may therefore return either conformance class. The
substitution finds nothing in a Transitional package, so no earlier result changes, and all
previous DOCX bytes are unchanged. LibreOffice renders of both inputs, and of the Docxodus reject
outputs before and after the fix, are in
[`docs/results/strict-revision-reject/`](results/strict-revision-reject/).

## An inserted chart whose part is Strict (Docxodus #1702)

`redline-v42` adds an original pair in the `packages` category. The original holds two
paragraphs; the revision inserts a paragraph between them that holds a bar chart (Alder, Birch,
Cedar, literal values, no workbook). The chart part names an annotation drawing, a text box
reading "Crates per week", through `c:userShapes/@r:id`. In the reproducer the chart part alone
is written in the Strict namespaces (`http://purl.oclc.org/ooxml/drawingml/chart`,
`…/drawingml/main` and `…/officeDocument/relationships`) while the main document, every
relationship type and the annotation drawing stay Transitional; the control's chart part is
Transitional too. Word 2024 (16.0.20326) opens both revisions and shows the chart, so a package
may mix the classes part by part. An annotation drawing stands in for the embedded workbook of
the issue's report because an authored package may hold only text and PNG entries.

Before the fix Docxodus followed a relationship attribute only in the Transitional namespace. It
copied the Strict chart part into the redline without its relationships part and without the
drawing, leaving `r:id="rShapes"` naming nothing. The semantic view does not read a chart part,
so the new `relationship-ids` assertion is the check that names the defect: `word/charts/…xml`
holds an id that names no relationship. Word 2024 refuses that redline ("The file appears to be
corrupted") and opens the redline written after the fix, where Accept All keeps the chart and
Reject All removes it. The control's redline passes the assertion and opens before and after.

Metric contract version 29 records the assertion. No earlier case declares it, so no earlier
result changes, and all previous DOCX bytes are unchanged. Word 2024 prints of both revisions and
of the Docxodus redline after the fix are in
[`docs/results/strict-chart-part/`](results/strict-chart-part/); the redline before the fix has
no print because Word does not open it. LibreOffice references and full-suite scoring are
pending.

## A deleted run that anchors a text box (Docxodus #1699)

`redline-v43` adds an original Hawthorn pair. A paragraph's second run anchors a text box, written
as Word writes it: a DrawingML shape in `mc:Choice` and its VML fallback, each holding the box's
story. In the reproducer the revision removes that run. In the control the box stays and the
paragraph after it is removed.

A text box is a story of its own, and the `w:del` around the anchoring run does not reach into
it. Desktop Word 2024 (16.0.20326), tracking the deletion of a text box, leaves the text inside
`w:txbxContent` as `w:t`; the authored redline is that shape. A redline that renames the box's
text to `w:delText` without a deletion inside the box does not open in Word ("The file appears to
be corrupted."), and so can be neither accepted nor rejected there. Before the fix Docxodus wrote
exactly that for the reproducer.

Neither round trip sees the defect, because the benchmark's engine restores every `w:delText` on
reject and drops the deleted run on accept, and the Open XML SDK reports nothing. The cases
therefore declare the new `deleted-text-owned` v1 assertion, recorded by metric contract
version 30. Word opened each case's inputs and authored redline, and resolved the authored
redlines to the expected documents with Accept All and Reject All.

| Case | Change | Docxodus before the fix | With the fix |
| --- | --- | --- | --- |
| `redline-deleted-textbox-text` | the run anchoring the box is deleted | two `w:delText` with no deletion in the box; Word refuses the file | box text stays `w:t`; Word opens, accepts and rejects |
| `redline-deleted-textbox-text-control` | the paragraph after the box is deleted | passes | passes |

The authored redlines of the earlier `redline-textbox-geometry` pair delete a whole text-box
carrier with the box's text renamed, the shape this assertion rejects. Those cases do not declare
it and their bytes are unchanged; correcting them is left to a separate change. LibreOffice was not
available where these cases were authored, so both comparisons are declared eligible and await the
calibration CI runs. All previous DOCX bytes are unchanged.

## Lists with picture bullets (Docxodus #1700)

`redline-v44` adds three original cases. A picture bullet is three linked pieces: a level's
`w:lvlPicBulletId`, the `w:numPicBullet` it names in the numbering part, and the image that bullet
names through the numbering part's relationships. A redline built on the original has to bring
all three for a list it takes from the revision.

- `redline-picture-bullet-inserted` (reproducer): the original has no numbering part; the revision
  adds a two-item list with a teal picture bullet.
- `redline-picture-bullet-shared-id` (reproducer): the original's list has a rust picture bullet and
  the revision replaces it with an unrelated list that has a teal one. Both documents number their
  picture bullet 0, so the imported bullet needs an id of its own.
- `redline-picture-bullet-symbol-control` (control): the first case with an ordinary bullet.

Accept/reject round trips, `untracked-text` and the new `picture-bullets` v1 check on both
endpoints are mandatory. The semantic view does not compare numbering, so the endpoints alone
cannot see a list drawn with the wrong picture or naming a bullet that is not there. Each authored
redline carries every bullet it needs under distinct ids. Word 2024 results and renders are in
[`docs/results/picture-bullets/`](results/picture-bullets/). The authored redlines were not run
through LibreOffice or the SDK validator on the capture machine; CI runs both.

## Section breaks both deleted and inserted (Docxodus #1757)

`redline-v48` adds two original cases. The original has three sections of quarry notes, each under
its own default header (`Quarry ledger 1` to `3`), and both revisions replace the whole body with
unrelated kiln notes.

- `redline-mixed-section-stories` (reproducer): the revision has two sections, each under its own
  header (`Kiln register 1`, `2`), so the comparison deletes two section breaks and inserts one.
  The review document holds four sections: the first kiln section, then the second kiln section's
  text with the first quarry section, then the second and third quarry sections.
- `redline-mixed-section-stories-deleted-control` (control): the revision has one section, so
  section breaks are only deleted.

Each review section's header pairs the headers of the sections whose text it holds. A section that
holds only quarry text disappears on accept, so its authored header is the quarry one, unchanged,
as Word 2024's own compare leaves it. Accept/reject round trips (whose semantic view lists each
section's header), `section-boundaries` on both endpoints and an exact `section-stories` list of the
review headers' text are mandatory. Docxodus 1d45d551 paired headers by section number once breaks
were both deleted and inserted, so its rejected reproducer has `Quarry ledger 2`, `3`, `3`. Word
2024 results and renders are in
[`docs/results/mixed-section-stories/`](results/mixed-section-stories/). LibreOffice was not
available on the capture machine; CI runs it.

## Values Strict writes in a form Transitional does not have (Docxodus #1758)

`redline-v49` adds an original Kiln pair in the `packages` category. The document holds a two-row
table whose header row carries `w:cnfStyle` on the row, both cells and both cell paragraphs, and a
rectangle filled with `4472C4` darkened by `a:lumMod`. The revision changes one word of the closing
paragraph. In the reproducer both inputs are Strict packages, written as a Strict save writes them:
`w:cnfStyle` holds only its twelve flags, `a:lumMod` is `val="50%"`, and the shape's `wps` elements
are folded into the `wordprocessingDrawing` namespace. The control is the same pair in the
Transitional class (`w:val="100000000000"`, `val="50000"`, a `wps` shape). Both authored redlines
are Transitional and write each value in its Transitional form.

The Open XML SDK validator reports nothing for any input. Before the fix Docxodus renamed a Strict
input's namespaces and kept its values, so the reproducer's redline carried five `w:cnfStyle` with
no `w:val`, which Transitional requires, and an `a:lumMod` of `50%`, which it types as an integer.
The mandatory `no-new-validation-errors` rule fails it on those six findings. The round trips and
`untracked-text` pass, because neither value is part of the semantic view. No new assertion is
needed. The control passes before and after.

No earlier case changes, and all previous DOCX bytes are unchanged. Results and renders of the
Docxodus redlines before and after the fix are in [`docs/results/strict-values/`](results/strict-values/).
LibreOffice references and full-suite scoring are pending.

## Tabs and line breaks (Docxodus #1759)

`redline-v50` adds five original reproducers and six controls. The reference compare treats a tab or a break
in a paragraph as it treats a space: it never keeps one unmarked on its own between changed words, and it keeps
one both versions share at the edge of a changed span. A comparison that instead treats tabs and breaks like
note references or images diffs every paragraph that holds one by all of its tokens, spaces included, and
threads short insertions and deletions around the kept spaces.

- `redline-tab-phrase-lead-tab` and `redline-tab-phrase-lead-break` (reproducers): one sentence in one run,
  after a tab or a line break, in which `logs tide charts` becomes `checks wind gauges and buoy lamps`. Control:
  `redline-tab-phrase-control`, the same sentence alone.
- `redline-tab-phrase-inner-tab` (reproducer): the same phrases with a tab between their second and third words,
  in a sentence of three runs and no punctuation, so no rule about lone punctuation decides whether the tab may
  stand on its own. Control: `redline-tab-phrase-inner-space-control`, a space in place of the tab.
- `redline-tab-comma-lead-tab` (reproducer): after a tab, `Ropes, nets and hooks are stowed.` becomes
  `Sails, oars and cleats are stowed.`; the shared comma goes with the replaced words. Control:
  `redline-tab-comma-control`, without the tab.
- `redline-tab-clause-tabbed` (reproducer): a clause laid out as tab, `(3)`, tab, text, rewritten in other
  words between unchanged paragraphs, is replaced whole. Control: `redline-tab-clause-control`, the clause as
  `(3) ` and its text in one run.
- `redline-tab-clause-edited-control`: a tabbed clause with two words changed stays one edited paragraph.
- `redline-tab-for-space-control`: a space replaced by a tab is itself the edit; the words around it stay
  unmarked.

The reproducers use the existing `revision-blocks` (each side's text one run in body order), `revision-text`
(`Ropes, nets` in adjacent deletions) and `untracked-text` assertions, so a redline that keeps a space, a tab or
the comma unmarked between one-word revisions fails while both round trips pass. The controls guard the
opposite mistakes: replacing an edited tabbed clause whole, or losing a tab that is the edit. Every LibreOffice
comparison is declared eligible; the authored redlines hold plain runs, tabs and line breaks inside ordinary
insertions and deletions, and whole-paragraph insertions and deletions. No earlier DOCX bytes change. Docxodus
`1d45d551` fails the five reproducers on their assertions alone and passes the controls; the fix passes all
eleven. See [the evidence and labelled review sheets](results/tab-break-edits/README.md).

## A removed header two sections share (Docxodus #1763)

`redline-v51` adds two original cases. The original has three sections of signal-tower notes and both
revisions keep the body and section breaks but reference no header at all.

- `redline-shared-header-removed` (reproducer): the original's first and third sections reference one header
  part (`Tower ledger`) and the second has its own (`Stair ledger`).
- `redline-shared-header-removed-own-control` (control): each section has its own part (`Tower ledger`,
  `Stair ledger`, `Chest ledger`).

Header references cannot be tracked, so a correct redline keeps a reference in every section and marks each
header's text deleted. The authored redlines give every section a part of its own, as the reference compare
does; a redline that keeps the shared part in both sections is equally correct. Reject must restore each
original header in place. Accept leaves each section's header story empty, so the accepted expectation is the
revision with those empty stories rather than the revision itself. Both round trips and an exact
`section-stories` list of the review headers' text (`Tower ledger`, `Stair ledger`, `Tower ledger`) are
mandatory, with `untracked-text` keeping the body unmarked. Docxodus `644bbc9a` writes an unchanged section
break with the revision's section properties and bound the shared part only where it reappeared, so its
redline's first section has no header: it fails both round trips and `section-stories` (observed `''`,
`Stair ledger`, `Tower ledger`) and passes the control. The fix passes both. See
[the evidence and labelled review sheets](results/shared-header-removal/README.md).

## Revision relationship ids and an inline title page (Docxodus #1771)

`redline-v52` adds five original cases. Each document has two sections of canal-lock notes; the first
section ends inside the body, at a paragraph that carries its section properties.

The first three give the original's sections the headers `Upper basin` (relationship id `rHeader1`) and
`Lower basin` (`rHeader2`), and change only how the revision names its header parts:

- `redline-revision-part-two-stories` (reproducer): the revision keeps `Upper basin` in the first section
  under a new id, `rHeader3`, and lets the second section inherit it. That one revision part pairs with two
  original stories: unchanged against the first section's, changed against the second's.
- `redline-header-ids-swapped` (reproducer): both headers are unchanged, but the revision gives `Upper basin`
  the id `rHeader2` and `Lower basin` the id `rHeader1`.
- `redline-header-ids-renamed-control` (control): both headers are unchanged under ids the original does not
  use.

In these two the revision also changes one word of the second section's text (`paddles` to `sluices`), so the
comparison has a change to record and copying either input fails a round trip.

Header references cannot be tracked, so a correct redline keeps a reference in every section, and in the
first reproducer the second section's story reads `Upper basin` once accepted: its accepted expectation is the
revision with `Upper basin` referenced from both sections. The other two accept to the revision itself. Both
round trips are mandatory, with `untracked-text` keeping the body unmarked. Docxodus `54eb5836` writes a section
break both documents share with the revision's references and resolves their ids in the original's package, or
through the output of whichever pair last used the revision part. Rejecting its first reproducer shows `Lower
basin` in both sections (`markup-rejected`); in the swapped case both sections show `Lower basin` on accept and
reject alike. It passes the control, where no revision id exists in the original. The fix keeps the original's
references on a section break both documents share and passes all three.

The other two give the first section a first-page header, `Gate register`, and a running header,
`Lock register`, which the second section inherits:

- `redline-inline-title-page-off` (reproducer): the original's first section has a title page (`w:titlePg`)
  and the revision's does not; nothing else changes.
- `redline-inline-title-page-off-margin-control` (control): the revision also raises that section's top
  margin from 1440 to 1800 twips.

The final section has no title page in either document, so neither case relies on the final section's
`w:sectPrChange`. A correct redline gives the first section the revision's properties and records the
original's in its `w:sectPrChange`. The markup view holds no section properties, so `section-flags` carries
the check: no title page in the review or the accepted document, and the first section's title page back in
the rejected one. Docxodus `54eb5836` compares an inline section break only on page size, margins, orientation
and section type under its default policy, so in the reproducer the paragraph is unchanged and its section
properties are copied without a record: the rejected flags are `false, false` instead of `true, false`. The
margin change in the control makes it record every property, and it passes. The fix records any differing
section property and passes both. See [the evidence and labelled review sheets](results/revision-part-two-stories/README.md).

## Values a section change leaves out (Docxodus #1775)

`redline-v53` adds seven original cases. Each document holds two paragraphs of harbour-ferry notes.

- `redline-section-orientation-default` (reproducer): the original's one section is portrait Letter and, as
  documents usually do, leaves `w:orient` at its default; the revision's is landscape.
- `redline-inline-section-orientation-default` (reproducer): the same change on the first of two sections,
  which ends at the first paragraph.
- `redline-section-orientation-stated-control` (control): the original writes `w:orient="portrait"` itself.
- `redline-section-title-page-off` (reproducer): the original's section has a title page (`w:titlePg`) and
  the revision leaves it out.
- `redline-section-title-page-off-stated-control` (control): the revision writes `<w:titlePg w:val="0"/>`
  itself.
- `redline-section-page-width-runs` (reproducer): only the page width of the first of two sections changes,
  from 12240 to 12000 twips; no run's formatting changes.
- `redline-section-page-width-runs-bold-control` (control): the paragraph that ends that section also turns
  bold.

The issue reports that a desktop word processor reads a value one side of a `w:sectPrChange` leaves out as
unchanged, not as its default: it rejects an archive without `w:orient` to landscape, and lists no revision,
and keeps the title page, for a final section without `w:titlePg` beside an archive that has it. This bench has no
capture of that application for these cases; the reproducers rest on the issue's report. Both round trips
pass such a redline, since the markup view holds no section properties and the benchmark's engine restores the
archive as written, so `section-change-values` reads the literal values: `landscape` in the section and
`portrait` in its archive, or a title page `off` in the section and `on` in the archive. The title-page cases
also declare `section-flags` on the review and both endpoints; the others declare the changed section's page size
in each resolved endpoint with `section-change-values`. Every case bounds `revision-count`: one record (the
section's), or two for the bold control. LibreOffice 25.8.7.3 exposes no revision
for a change to section properties alone, so its comparisons are declared ineligible for every case but the
bold control. The same holds for the two #1771 inline title-page cases, whose LibreOffice comparisons were declared
eligible and left them unmeasured; they are now declared ineligible too, with no change to their documents.

Docxodus `d99765d7` archives each side's properties as written: the orientation reproducers read `landscape`
and null, the title-page reproducer null and `on`, and the page-width reproducer (and the inline orientation
reproducer) counts two records, because
every run of a paragraph classed as changed only in its formatting received an empty `w:rPrChange`. It passes
the three controls. The fix states, on each side, every value the other side states where leaving it out
means a value the specification defines, and marks only a run whose formatting changed; it passes all seven.
See [the evidence](results/section-change-values/README.md).

## Formatting restored to its own run (Docxodus #1784)

`redline-v54` adds four original cases. In each, the revision centres a one-paragraph document and removes the
formatting of some of its runs; the text is unchanged, so a correct redline records a `w:pPrChange` and, on each
run that lost its formatting, a `w:rPrChange` holding that run's own original properties.

- `redline-format-only-symbol` (reproducer): a symbol (`w:sym`) run comes before the bold run.
- `redline-format-only-tab` (reproducer): an underlined tab run comes before the bold run.
- `redline-format-only-hyperlink` (reproducer): the bold run is inside a hyperlink.
- `redline-format-only-plain-control` (control): plain text runs only.

Every case opens with the same bookmark; the tab case's tab is also underlined, a second reformatted run, and its
tab takes the place of the space after `Lead`.

`run-formatting` declares the bold and underline of the text spans of both endpoints, and `revision-count` bounds the redline to the
paragraph change and one record per reformatted run. Docxodus `6c98b822` located each run's original formatting with a
cursor that counted only `w:t` text, while a symbol counts as one character: rejecting the symbol case left `bold`
plain and made ` plain tail` bold. The tab case gave the tab the bold run's properties instead of its underline, and
the hyperlink case never marked the linked run, so its bold moved to the run after it. It passes the control. The
fix (`c3df4729`) finds each run's formatting at the same place in the original's run model, and splits a run Word re-split, and passes all four. See
[the evidence](results/format-only-run-formatting/README.md).

## Paragraph marks and indented copies (Docxodus #1794, #1793)

`redline-v55` adds six original cases.

- `redline-mark-size-blank` (reproducer): an empty paragraph between two lighthouse notes; the revision grows its
  mark to 36pt (`w:sz w:val="72"`) and changes nothing else.
- `redline-mark-size-leading-blanks` (reproducer): the same change on three empty paragraphs at the top of the
  document.
- `redline-mark-size-text` (reproducer): the same change on the mark of the second note, a paragraph with text.
- `redline-mark-size-centred-control` (control): the same change on the same empty paragraph, which the revision
  also centres, so the paragraph's own properties change too.
- `redline-indented-copy` (reproducer): the revision changes "dusk" to "dawn" in a table cell and indents
  property elements, putting a newline and two spaces before each of their children (nested children are not
  indented deeper): the properties of a field-result run (`w:rPr` holding only
  `w:noProof`), a paragraph mark, the table and cell properties and the section. Paragraph and run content stay
  compact.
- `redline-indented-copy-control` (control): the same one-word edit without indentation.

The mark cases declare every paragraph mark's size in both endpoints with `mark-formatting`, and each case bounds
`revision-count` to its own records: one per changed mark, plus the paragraph-property change in the control, and the
edit's deletion and insertion in the indented pair.

LibreOffice 25.8.7.3 shows the authored mark change on an empty paragraph as a revision, so those cases keep both
LibreOffice comparisons, but its text view cannot see a mark, so those comparisons add nothing the text view can see. It shows
no revision for the mark-only change on a text paragraph, so `redline-mark-size-text` declares both comparisons
ineligible; markup endpoints, declared marks, revision count and SDK checks stay mandatory.

Docxodus `9704704e` paired paragraphs without their marks, so it recorded no mark change and rejected to the 36pt
marks. Its IR hash kept indentation between elements, so it read three of the indented elements as changed: the
field-result run's properties (it deleted and reinserted the field's paragraph, rewritten as a complex field), the
table properties and the section. The indented mark and cell properties changed nothing for it and are there for
realism. It passes both controls. [JSv4/Docxodus#1798](https://github.com/JSv4/Docxodus/pull/1798) (#1794) passes the
mark cases and [JSv4/Docxodus#1799](https://github.com/JSv4/Docxodus/pull/1799) (#1793) the indented pair; each
passes both controls, and the head of #1799, which carries both, passes all six. See
[the evidence](results/mark-formatting-and-indentation/README.md).

## Formatting inside table cells and untyped story references (Docxodus #1797, #1803)

`redline-v56` adds nine original cases. The first five share a two-by-two table of harbor notes between an
opening and a closing paragraph.

- `redline-cell-bold` (reproducer): the revision bolds the second cell's run and changes nothing else.
- `redline-cell-mark-size` (reproducer): the second cell ends with an empty paragraph; the revision grows its mark
  to 36pt (`w:sz w:val="72"`) and changes nothing else.
- `redline-cell-bold-beside-edit` (reproducer): the revision changes "noon" to "dawn" in the first cell and bolds
  the second cell's run and the last cell's, whose row has no other change.
- `redline-cell-bold-edit-control` (control): the revision bolds the second cell's run and changes "dusk" to "dawn"
  in that same cell, so the cell's text changes too.
- `redline-cell-mark-size-edit-control` (control): the revision grows the same empty paragraph's mark and changes
  "dusk" to "dawn" in that cell.
- `redline-untyped-header-changed` (reproducer): one section whose header is referenced without `w:type`; the
  revision adds " revised" to the header.
- `redline-untyped-footer-changed` (reproducer): the same change to a footer referenced without `w:type`.
- `redline-typed-header-changed-control` and `redline-typed-footer-changed-control` (controls): the same change
  to a header or footer referenced with `w:type="default"`.

Neither round trip reads character formatting or paragraph marks, and LibreOffice's text view cannot see them
either, so every cell case declares the spans of every supported run property with `run-formatting` and every
paragraph mark's properties with `mark-formatting` in both endpoints; a redline that adds untracked formatting fails
too. Each case bounds `revision-count` to its own records, and the edited cells' unchanged text is declared
untracked, so replacing a whole cell fails. No assertion reads a paragraph's own properties inside a table cell, so the
third shape #1797 reports, a cell paragraph's alignment, is not pinned here. The story cases read the section's
single default reference and the story text it reaches with `section-stories`.

The schema requires `w:type` on a header or footer reference, and the SDK validator reports both endpoints of the
untyped cases; validity is judged against the inputs, so it stays a valid check of the redline. LibreOffice 25.8.7.3
does not import a reference without `w:type`: the exported PDF of either endpoint has no header or footer, and the
authored redline exposes no revision, so both untyped cases declare their LibreOffice comparisons ineligible. It also
shows no revision for the mark-only change in the cell, so `redline-cell-mark-size` declares both comparisons
ineligible. Markup endpoints, declared formatting, the section story, revision counts and SDK checks stay mandatory
in all three.

Docxodus `fbabfaf4` compared a table's cells by their text alone, so it recorded none of the cell formatting
changes and rejected to the revised formatting; it passes both cell controls, whose cell text changes. Binding the
changed story to its section looked for a literal `w:type="default"`, so it added a typed default reference beside
the untyped one and the section held two; it passes both typed controls. The fixes are
[JSv4/Docxodus#1807](https://github.com/JSv4/Docxodus/pull/1807) (#1797) and
[JSv4/Docxodus#1806](https://github.com/JSv4/Docxodus/pull/1806) (#1803). See
[the evidence](results/cell-formatting-and-untyped-story-references/README.md).

## Content-control rows and a removed section break (Docxodus #1804, #1805)

`redline-v57` adds six reproducers and six controls. Metric contract 35 adds `table-state` v3.

**Rows and cells in content controls (#1804).** Eight cases share a two-column, fixed-width table of depot notes
(`Depot`/`Platform one`, `Signal`/`Lamp two`, and in two cases `Siding`/`Buffer three`) and a closing paragraph.
Each reproducer puts a row in a table-level content control (`w:tbl/w:sdt/w:tr`, the shape a repeating section
writes) or a cell in a row-level one (`w:tr/w:sdt/w:tc`); its control is the same case with no content control.

| Reproducer | The revision | Control |
| --- | --- | --- |
| `redline-control-row-beside-edit` | adds a word to the first row; the second row sits in a control | `redline-plain-row-beside-edit-control` |
| `redline-control-removed` | removes a control holding the second and third rows | `redline-plain-rows-removed-control` |
| `redline-control-cell-same-row` | adds a word to the first cell of a row whose second cell sits in a control | `redline-plain-cell-same-row-control` |
| `redline-control-row-bold` | bolds the text of the second row's second cell, in a control, and changes nothing else | `redline-plain-row-bold-control` |

A correct redline writes each row or cell once, inside its control, with its edits tracked. A control only one
document has is marked with the paired custom-XML ranges Word writes around a whole control, so the view without it
drops the control with its rows (`redline-control-removed`'s authored redline crosses the control's opening and
closing tags with `w:customXmlDelRangeStart`/`End`, as the block-level control cases do). The markup view looks
through a table's content controls, so it cannot see a lost or doubled control. `table-state` v3 can: it reads a
table's rows through table-level controls and adds a `control` entry to every row, the `w:id` of each control
around it, outermost first and joined by `/`, or null; a later control that reuses an id is named with `#2`, `#3`, …,
so one control written twice does not read as one. Cells are read as in v2. Unlike v1 and v2 it may be declared on
an accepted or rejected endpoint. A control left holding no row is a row with no cells, so it cannot match a
declared state. Every case declares the state of both endpoints and bounds `revision-count`; the bold cases also
declare `run-formatting`.

**A removed section break (#1805).** Four cases hold two paragraphs of depot notes and one header or footer part,
`Depot timetable`. In the original the first paragraph's break names the story and the last section inherits it;
the revision keeps both paragraphs in one section, whose break names the story.

| Case | Kind | The revision |
| --- | --- | --- |
| `redline-removed-break-inherited-header` | reproducer | removes the break and adds `, winter` to the header |
| `redline-removed-break-inherited-footer` | reproducer | removes the break; the footer is unchanged |
| `redline-removed-break-named-header-control` | control | as the header reproducer, but the original's last section names the header itself |
| `redline-removed-break-deleted-paragraph-control` | control | deletes the paragraph holding the break and adds `, winter` to the header |

A correct redline draws the kept paragraph as the original's copy, with its break, deleted and the revision's copy
inserted. Header references cannot be tracked, so it keeps a reference in every section: the original's last
section names the story itself, and the rejected expectation of each case but the named control is the original
with that reference written out, which shows the same story. `section-stories` reads both sections of the raw
redline. LibreOffice 25.8.7.3 keeps an empty paragraph and its section break when it accepts the authored deleted
paragraph that holds the break, so its accepted document has two sections; the four cases declare that one
LibreOffice comparison ineligible and keep the rejected one.

| Case | Kind | Baseline `f5cefdd1` | #1805 fix `1b7689b0` | #1804 fix `29bbb623` | Both fixes `77cfa753` |
| --- | --- | --- | --- | --- | --- |
| `redline-control-row-beside-edit` | reproducer | `assertion-table-state`, `libreoffice-accepted`, `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | `assertion-table-state`, `libreoffice-accepted`, `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | none | none |
| `redline-plain-row-beside-edit-control` | control | none | none | none | none |
| `redline-control-removed` | reproducer | `assertion-table-state`, `libreoffice-rejected` | `assertion-table-state`, `libreoffice-rejected` | none | none |
| `redline-plain-rows-removed-control` | control | none | none | none | none |
| `redline-control-cell-same-row` | reproducer | `assertion-revision-count`, `assertion-untracked-text` | `assertion-revision-count`, `assertion-untracked-text` | none | none |
| `redline-plain-cell-same-row-control` | control | none | none | none | none |
| `redline-control-row-bold` | reproducer | `assertion-run-formatting` | `assertion-run-formatting` | none | none |
| `redline-plain-row-bold-control` | control | none | none | none | none |
| `redline-removed-break-inherited-header` | reproducer | `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | none | `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | none |
| `redline-removed-break-inherited-footer` | reproducer | `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | none | `libreoffice-rejected`, `markup-accepted`, `markup-rejected` | none |
| `redline-removed-break-named-header-control` | control | none | none | none | none |
| `redline-removed-break-deleted-paragraph-control` | control | none | none | none | none |

Each cell lists the failed checks. The fix commits are the heads of
[JSv4/Docxodus#1808](https://github.com/JSv4/Docxodus/pull/1808) (#1805) and
[JSv4/Docxodus#1811](https://github.com/JSv4/Docxodus/pull/1811) (#1804). `77cfa753` is a merge of the two,
made only for scoring. The authored redlines pass every check. See
[the evidence and labelled review sheets](results/content-control-rows-and-removed-breaks/README.md).
