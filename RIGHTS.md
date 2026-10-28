# Authorship and artifact rights

John Scrudato IV owns the original harness, adapter, documentation, fixture generator, text, and diamond graphic authored for this repository. The MIT license covers these files and the generated DOCX fixtures. No document templates, input documents, corpus downloads, embedded font files, or vendored libraries are included.

`bench/fixtures.py` is the complete source of every PDF-track fixture, and `bench/redline_fixtures.py` of every redline-track input, expected document and authored redline under `fixtures/redline/`. It constructs OOXML packages from literal text and generates the diamond image from pixel coordinates. `fixtures/manifest.json` records each document hash, generator hash, author, license, origin, asset statement, expected text, and assertions. CI regenerates every package and compares the bytes.

Authored packages hold no external resources and no embedded font programs; `bench/audit.py` (`check_package`) enforces this on every regenerated package. Two narrowly declared shapes are permitted, because cases about the package itself need them. An external hyperlink relationship from the main document may name a target on the reserved `example.com` domain (a `mailto:` listing lower-case `@example.com` addresses, or a plain `https://example.com/` path, with no query, port or percent-encoding): such a target is a navigation address that no renderer or harness loads, and it names no real party. The font table may carry an embedded-font relationship whose target part holds exactly `PLACEHOLDER_FONT_BYTES` from `bench/common.py`, a one-line ASCII string stating that it is not a font program. Every font relationship must come from the font table and reach those bytes, whatever its target is named, and every part a font-program content type (by Default extension or Override, parameters ignored) types must hold them too; part names, relationship types and content types are compared case-insensitively. Independently of all metadata, every entry's bytes must be text (UTF-8 with no NUL byte, which covers XML), a complete PNG, or the placeholder: a font program, obfuscated or compressed, always has NUL bytes in its table directory, so an orphan one is refused whatever it is called. Any other external relationship, font relationship, font-typed or font-named entry, or binary entry is still refused.

Contributions must include an author and rights record. Adding an asset requires a generator or an individually reviewed origin and redistribution grant. Git tracking alone is insufficient. Inputs are never fetched from a corpus service. Fixtures are immutable during rendering.

The harness uses the Python standard library. Its opt-in PDF dot-leader token policy verifies these authored package sources and preserves raw PDF word geometry and raster evidence. This includes the independent delivered-HTML attribute inspector in `bench/html_artifacts.py`. The redline track's adapter (`adapters/docxodus-redline`) and validation tool (`tools/ooxml-validator`) are original C# sources; they are compiled outside the source tree against a separately provisioned Docxodus checkout and the DocumentFormat.OpenXml NuGet package (MIT), neither of which is copied here. LibreOffice, Poppler, qpdf, fontconfig, Node.js, and Docxodus are separately provisioned executables or renderer packages; their implementations are not copied into this repository. Their own licenses continue to apply: [LibreOffice MPL-2.0 and its distributed component notices](https://www.libreoffice.org/licenses/), Poppler GPL-2.0 or GPL-3.0 as recorded in the installed package's copyright inventory, [qpdf Apache-2.0](https://qpdf.readthedocs.io/en/stable/license.html), fontconfig MIT, Node.js MIT with its distributed notices, and Docxodus MIT with its package notices. The benchmark invokes them through process or public API boundaries. Installation does not change their licensing; consult each installed distribution's complete notices.

The core documents request Liberation Serif, except for the explicitly named Times New Roman agreement variant. Install the unmodified Liberation font package separately and retain its [SIL Open Font License notices](https://github.com/liberationfonts/liberation-fonts/blob/main/LICENSE). Provision Times New Roman separately under its own license; the rendering workflow uses `ttf-mscorefonts-installer` and accepts the Core Fonts for the Web EULA. Font binaries are not committed or covered by this repository's MIT license. See Microsoft's [font redistribution and document embedding guidance](https://learn.microsoft.com/en-us/typography/fonts/font-faq). A run records the exact regular, bold, italic, and bold-italic file hashes, rejects family substitution, and checks PDF font identities. Generated reference and candidate PDFs can contain font subsets; retain the recorded font contract with the artifact bundle.

Before registering operator-captured Word PDFs, approve the input, image, font embedding, and artifact-publication rights. Capture metadata must explicitly attest approval. Generated reports and PDF bundles stay outside the source tree and are published as CI artifacts. This file describes the included inventory and process; it does not extend the license of separately installed software.

The footer-frame reproduction and ordinary-flow control are original literal-text OOXML generated entirely by `bench/fixtures.py`, with no imported document content.

The long-comment reproduction, short-note control and DOM observer are original work authored in this repository. All comment words, author metadata and OOXML are generated here. No renderer fixtures or content are imported.

The nested-reply, flat-note and author-header cases are original literal-text OOXML authored by `bench/fixtures.py`. Their comment graph, author names and dates are generated here; no external or renderer fixture content is used.

The durable timestamp and date-caption fixtures are original literal-text OOXML authored by `bench/fixtures.py`. All comment content, metadata and identifiers are generated here; no renderer fixtures are imported.

The comment-return and ordinary body-bookmark fixtures are original literal-text OOXML authored by `bench/fixtures.py`. All phrases, comment metadata and bookmark identifiers are generated here; no renderer fixture or external document content is imported.

The CSS selector pair for Docxodus #1230 uses newly authored Pine text and generated OOXML.
Both cases share original DOCX bytes and use no third-party text, graphics or embedded fonts.

The Times New Roman agreement variant for bench #33 reuses this repository's original agreement text and OOXML. Only its requested font family changes; it contains no embedded font files or imported document content.

The consolidated-field fixtures for Docxodus #1206 use original Alder/Birch text and literal OOXML authored here. Source documents, expected final/original views and authored redlines contain no imported renderer fixtures or third-party document content.

The fitting nested footnote table and ordinary-table control for Docxodus #1217 are original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The run-in keep pair for Docxodus #1294 is original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The default tab interval cases for Docxodus #1269 are original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The table-placement cases for Docxodus #1219 and #1244 are original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported. Their Word for the web reference PDFs were exported by the repository owner from these exact inputs.

The endnote-format and floating-picture section-change pairs for Docxodus #1314 are original literal-text OOXML generated by `bench/fixtures.py`; their text, reviewer metadata, section properties and the generated diamond picture are authored here, and no renderer fixtures or third-party content are imported.

The screenshots in `docs/results/pending-section-change/` are page renders of the #1314 section-change inputs above, by LibreOffice 25.8.7.3 and Docxodus, taken from this repository's render CI runs 39942526470 and 39942538985.

The deleted-footer-field pair for Docxodus #1272 is original literal-text OOXML generated by `bench/fixtures.py`; its Rowan text, reviewer metadata and fields are authored here, and no renderer fixtures or third-party content are imported.

The screenshot sheets under `docs/results/deleted-page-field/` crop the footer band from this repository's own CI render evidence (runs 39906312404 and 39911469648) of the two deleted-page-field fixtures: LibreOffice reference rasters and Docxodus candidate rasters of original fixture text. No third-party content is included.
The footnote formatting-revision pair for Docxodus #1271 is original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The screenshot sheets in `docs/results/note-format-revision/` show LibreOffice and Docxodus renders of the original footnote formatting-revision pair above. No third-party document content is included.

The inline-drawing set for Docxodus #1270 is original literal-text OOXML generated by `bench/fixtures.py`: its shape, group and tracked-deletion markup, its text and the teal raster of its picture control are authored here, and no renderer fixtures or third-party content are imported. The screenshots in `docs/results/inline-drawing-shapes/` are page renders of these inputs by LibreOffice 25.8.7.3 and Docxodus, taken for review.

The leader-line fixtures for Docxodus #1275 (right stop inside the right indent, inline markup, and their plain control) are original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The six screenshots under `docs/results/right-tab-leader-lines/` show this repository's original #1275 fixtures, rendered by LibreOffice 25.8.7.3 and Docxodus f34d9b4d in CI run 39560008323 (artifact 12330606248, bench source 5df978cd4ed212666251ec8c75ede64350e66fbb). They are copied byte-for-byte from the candidate run's page-1 evidence; no third-party document content is included.

The leader-line fixtures for Docxodus #1285 (`PAGEREF` page numbers, wrapping titles, a second stop inside the right indent, bookmarks inside links, a long suffix after an overhanging stop, and their controls) are original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The nine screenshot sheets under `docs/results/right-tab-gaps/` show this repository's original #1285 inputs in fresh LibreOffice 25.8.7.3 and Docxodus 466ee317 public-export captures. Each page-one feature band is rasterized at 96 DPI and displayed at its original size beside the other renderer, with HTML-generated labels. `capture.json` records the exact inputs, renderer and limitations. No third-party document content is included.

The Strict semantic-limit pair for Docxodus #1352 is original literal-text OOXML generated by
`bench/redline_fixtures.py`. Its Marsh station agreement text, conformance variants and expected
redlines are authored here; no renderer fixtures or third-party content are imported. The
labelled screenshot sheets under `docs/results/strict-semantic-limits/` show LibreOffice 25.8.7.3
page rasters of these original inputs and Docxodus comparison outputs, with recorded API outcomes.

The column-width revision quartet for Docxodus #1322 is original literal-text OOXML authored by
`bench/redline_fixtures.py`. Gauge labels, grids, width properties and expected native revisions
are generated here. No renderer fixtures or third-party content are imported. The labelled
screenshot sheets under `docs/results/column-width-revisions/` are LibreOffice 25.8.7.3 page
rasters of Docxodus outputs from these original inputs, with recorded schema and registry outcomes.

The pending-grid column-edit cases for Docxodus #1342 are original literal-text OOXML authored
by `bench/redline_fixtures.py`. Survey marker labels, grid histories, shading, row heights and
expected resolved documents are generated here. No product fixtures or third-party document
content are imported. The labelled sheets under `docs/results/pending-grid-columns/` show
LibreOffice 25.8.7.3 PDF rasters of candidate outputs from these original cases.

The block-insertion cases for Docxodus #1331 are original literal-text OOXML authored by
`bench/redline_fixtures.py`. Harbor labels, the shaded table and independent expected outputs
are generated here. No product fixture or third-party content is imported. The labelled sheets
under `docs/results/block-insertion/` are LibreOffice 25.8.7.3 PDF rasters of candidate outputs.

The mixed-run text-edit cases for Docxodus #1337 are original OOXML authored by
`bench/redline_fixtures.py`. Marina labels, split words, marker positions and independent
expected redlines are generated here. No product fixtures or third-party document content
are imported. The sheets under `docs/results/mixed-run-edits/` rasterize the candidate
outputs after LibreOffice 25.8.7.3 rejection, followed by its PDF export.

The tracked-column gap cases for Docxodus #1330 are original literal-text OOXML authored by
`bench/redline_fixtures.py`. Waterway marker labels, nonuniform widths, omitted/merged rows
and expected resolved packages are generated here. No product fixtures or third-party content
are imported. The sheets under `docs/results/tracked-column-gaps/` are LibreOffice 25.8.7.3 PDF
rasters of actual saved candidates after the declared native review attempt, including its
unresolved output when that review fails.

The adjacent-table property cases for Docxodus #1341 are original literal OOXML authored by
`bench/fixtures.py`. Estuary and pier labels, nonuniform widths, colored borders and cell margins
are generated here. No product fixtures or third-party content are imported. Capture sheets under
`docs/results/adjacent-table-properties/` compare actual production PDFs with LibreOffice PDFs;
they do not claim to be Word references.

The literal-text tab cases for Docxodus #1353 are original OOXML authored by `bench/fixtures.py`.
Estuary labels, run formatting, tab stops, running stories and controls are generated here. No product
fixtures or third-party documents are imported. Capture sheets under `docs/results/literal-text-tabs/`
show the authored LibreOffice reference and labelled Docxodus diagnostic PDFs; no font files are embedded.

The story-comment cases for Docxodus #1310 reuse original literal-text OOXML from branch
`fixtures/story-comments` (8bbf090): the ledger text, reviewer metadata and comment are authored
in this repository. No product fixtures or third-party document content are imported. New labelled
captures under `docs/results/story-comments/` rasterize these original inputs.

The eleven floating-shape fixtures for Docxodus #1346 are original literal-text OOXML generated by `bench/fixtures.py`. Their Harbor text, DrawingML rectangle/group/hexagon, explicit wrapping and stacking values, and plain VML rectangle are authored here. They contain no imported document content, third-party graphics, or embedded fonts. Existing inline-drawing inputs supply unchanged controls.

The labelled sheets under `docs/results/floating-shapes/` rasterize these original floating-shape inputs with LibreOffice and Docxodus. The screenshots contain the authored document text and generated geometry; no font files or third-party document content are distributed.

The seven Summit reviewer-account cases for Docxodus #1317 are original literal-text OOXML
created by `bench/redline_fixtures.py`. Their people metadata, account identifiers, comments,
expected documents and authored redlines are generated here. The raw-package inspector and its
negative controls are original work. No renderer fixture, external document, font binary or
third-party text is imported.

The seven review sheets under `docs/results/revision-ownership/` show these original Summit packages through Docxodus's public review renderer, together with independently read metadata and original labels. Their source/output hashes and method are recorded in `capture.json`; no third-party document content is included.

The six move-range rejection cases for Docxodus #1340 use original literal-text OOXML authored in
`bench/redline_fixtures.py`. Their expected paragraphs follow independently observed native Word
results on the corresponding original core probes. No native Word package, renderer fixture,
external document content, image or embedded font is imported into this corpus.

The #1339 Times New Roman exact-zero and positive-height row fixtures reuse the original literal-text
OOXML authored in commit 7851026 of this repository. Their bytes exactly match the source packages
used for the native Word captures. There are no imported document contents, images or embedded font
files. Native PDF font subsets remain governed by the separately provisioned font license and the
recorded reference font contract; no font binaries are redistributed.


The #1201 Times New Roman zero-width column fixture and 24pt control reuse original literal-text
OOXML authored in the row-geometry branch. The package bytes match the separately retained native
Word inputs. No external document content, images, or font binaries are imported. Rendered evidence
contains original fixture text and separately licensed font subsets; the font contract and native
capture hashes are retained with the unmodified local Word references.

The thirteen #1202 oversized-block cases reuse six original row-geometry cases and add seven
original literal-text OOXML probes in `bench/fixtures.py`. They contain no renderer fixtures,
external document content, images, or embedded font binaries. The labelled evidence sheets in
`docs/results/oversized-page-blocks/` show these authored inputs and separately authored core probes
in native Word and public Docxodus exports. Native font subsets retain the recorded font contract;
no font binaries are redistributed.

The eight #1217 note-table flow cases reuse original literal-text OOXML from the author's
`80ac8d7` prototype, with Times New Roman declared for the preserved Word captures. Their exact
input bytes are reproducible by this repository's generator. Native/candidate comparison PNGs
and PDF inspections show only these authored fixtures. No external document, template or standalone
font binary is imported; native PDF font subsets retain the separately provisioned font license.

The nineteen #1217 kept-citation and dense-chain cases reproduce original literal OOXML authored
for the issue and the original keep/widow/separator controls. The six-part packages are generated
here without imported documents or templates. Comparison PNGs and PDF inspections in
`docs/results/kept-note-flow/` show only these authored fixtures. No authentication data or
standalone font binaries are included; the separately provisioned native PDF font subsets retain
the recorded font contract.

The fourteen #1217 kept-note paragraph cases in `core-v69` reproduce original literal OOXML and
font declarations for separately retained native Word captures. The long variants use authored
unbreakable body/note labels and explicit note breaks, so the unchanged complete-token contract
can adjudicate them without merging legal native wraps. All source packages regenerate exactly.
Comparison PNGs and PDF inspections under `docs/results/kept-note-paragraphs/` contain only these
authored fixtures. No external documents, authentication data or standalone font binaries are
included; native PDF font subsets retain the separately provisioned font contract.


The two #1124 justification-line cases in `core-v70` reproduce original literal OOXML and prose authored for independently captured native Word controls. Integer twip widths preserve all 45 held-out paragraphs without importing a font library or template. Both inputs regenerate byte for byte. Native/candidate PNGs and raw PDF inspections under `docs/results/justification-lines/` contain only this original text. No standalone font binary, external document or authentication data is included; native PDF font subsets retain the separately provisioned font contract.

The three #1124 native text precision inputs in `core-v71` reproduce original literal OOXML and text authored for Word capture. Their glyph, word-gap and eight long-paragraph controls regenerate byte for byte without a font library, template or imported document. Native/candidate PNGs and PDF coordinate inspections under `docs/results/native-text-precision/` contain only this original text. No standalone font binary or authentication data is included. Times New Roman and Arial are separately provisioned; native font subsets retain the recorded family contract and do not establish identical font versions or rasterization.

The optional Word font-binding inspector and its synthetic contract tests are original
standard-library code. External operator-captured reference packs may contain separately
licensed embedded fonts only with reviewed rights, source/program hashes and retained
license notices; those packs remain outside this repository's source inventory. A reviewed
glyph-identity attestation qualifies an exact captured font program, not a font-name alias
or an arbitrary replacement family. This change vendors no font binary or third-party
source document and does not alter the authored corpus or its fixture generation.

The full-page raster comparisons under `docs/results/word-reference-tracks/` show
only this repository's original authored text and diamond. They contain no font
program binaries, authentication material or external document content. Native
PDFs and source font parts remain in the separately licensed external capture
pack; its OFL notices and exact source/program audit bindings are retained there.
