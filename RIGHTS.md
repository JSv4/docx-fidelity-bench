# Authorship and artifact rights

John Scrudato IV owns the original harness, adapter, documentation, fixture generator, text, and diamond graphic authored for this repository. The MIT license covers these files and the generated DOCX fixtures. No document templates, input documents, corpus downloads, embedded font files, or vendored libraries are included.

`bench/fixtures.py` is the complete source of every PDF-track fixture, and `bench/redline_fixtures.py` of every redline-track input, expected document and authored redline under `fixtures/redline/`. It constructs OOXML packages from literal text and generates the diamond image from pixel coordinates. `fixtures/manifest.json` records each document hash, generator hash, author, license, origin, asset statement, expected text, and assertions. CI regenerates every package and compares the bytes.

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

The endnote-format and floating-picture section-change pairs for Docxodus #1314 are original literal-text OOXML generated by `bench/fixtures.py`; their text, reviewer metadata, section properties and the generated diamond picture are authored here, and no renderer fixtures or third-party content are imported.

The screenshots in `docs/results/pending-section-change/` are page renders of the #1314 section-change inputs above, by LibreOffice 25.8.7.3 and Docxodus, taken from this repository's render CI runs 39942526470 and 39942538985.

The deleted-footer-field pair for Docxodus #1272 is original literal-text OOXML generated by `bench/fixtures.py`; its Rowan text, reviewer metadata and fields are authored here, and no renderer fixtures or third-party content are imported.

The screenshot sheets under `docs/results/deleted-page-field/` crop the footer band from this repository's own CI render evidence (runs 39906312404 and 39911469648) of the two deleted-page-field fixtures: LibreOffice reference rasters and Docxodus candidate rasters of original fixture text. No third-party content is included.
The footnote formatting-revision pair for Docxodus #1271 is original literal-text OOXML generated by `bench/fixtures.py`; no renderer fixtures or third-party content are imported.

The screenshot sheets in `docs/results/note-format-revision/` show LibreOffice and Docxodus renders of the original footnote formatting-revision pair above. No third-party document content is included.
