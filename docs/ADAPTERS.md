# Renderer adapter protocol

Protocol version 1 uses one JSON request on stdin and one JSON response on stdout. The runner invokes an explicit command vector without a shell. Fixture records cannot select executable commands. Add adapter selection in `bench/__main__.py`; metrics and fixture IDs stay unchanged.

The request contains `protocol`, absolute `input` and `output` paths, `inputSha256`, a production `report` destination, an explicit `profile` (`review`, `comments`, optional `markupPresentation`), `fontDirectories`, exact `candidate` identity, and `timeoutMs`. `markupPresentation: "word"` selects Word-style tracked-change appearance for a markup review profile; omitting it retains the renderer default. The input is immutable. Output paths are new and must not be overwritten. The renderer must use the declared fonts and view.

An `ok` response contains `protocol: 1`, `status: "ok"`, `pdfSha256`, and `renderer` identity. Candidate PDF bytes must exist at the requested path and match the digest. Include candidate source/build identity and runtime identity. The Docxodus adapter retains a complete production report and source-bound build record.

A known conversion or unsupported-feature failure returns `status: "failed"` and structured `error`; the case scores zero. An unavailable host, unverifiable build, or unsuitable capture environment returns `status: "unmeasured"` and the reason; complete coverage is blocked. The runner independently reads the produced PDF and scores it. Internal layout metadata cannot substitute for that evidence.

`bench build-docxodus` builds only production WASM/TypeScript and public export assets, then writes `.docx-bench-build.json` in the separately provisioned renderer checkout. The adapter checks source commit/tree, clean tracked files, Node version, module path, build recipe, lockfiles, and build artifact hashes. It checks the supported sandboxed export runtime and configured fonts. It does not run renderer test suites or import their fixtures.

## Redline adapters

PDF cases may declare `preparation: {operation: "build" | "compare", inputs: [{path, sha256}, ...]}`.
`build` takes at least two sources; `compare` takes exactly two, original then revised, and uses
the existing public `DocxCompare.Compare` adapter. The declared review profile resolves the resulting
redline during production export, so both final and original views can be measured.
Their ordinary `input` is an independently authored expected document used for reference capture;
it is never substituted for a candidate build. The harness invokes the existing native adapter's
`build` operation, verifies its source-bound build and source digests, retains `candidate.docx`,
then renders those bytes through the public WASM/PDF path with the remaining conversion deadline.
The operation uses `DocumentBuilder.BuildDocument` with `KeepSections=false` for every source.
The harness independently checks that the built package has unique style IDs; a duplicate is a
measured preparation failure, even if a PDF renderer would tolerate the invalid package.
Set `DOCXODUS_OPERATION_BUILD` to a directory produced by `bench redline build-docxodus` at the
same candidate commit. Missing operation support is unmeasured. `libreoffice-reference` calibrates
the authored composite's PDF only; it does not attest the document-building operation.
Preparation source packages follow the same generation, rights, digest and external-resource
checks as ordinary PDF inputs. Build identity and the produced package digest accompany each result.

The redline track uses its own protocol version 1. The request carries `protocol`, `operation` (`compare`, `consolidate` or `reject`), `inputs` (absolute `path`, `sha256` and, for consolidation reviewers, `author`), a new `output` path and fixed `settings` (`author`, `date`). An `ok` response carries `status`, `outputSha256` and `engine` identity; `failed` and `unmeasured` carry a structured `error` with the phase that failed. The harness re-verifies the output digest and the unchanged inputs. `adapters/docxodus-redline` is the Docxodus implementation; it is compiled from a clean, exact-commit checkout by `bench redline build-docxodus`, and the harness checks that build record, not the adapter, before each case. See [the redline scoring contract](REDLINE.md).

## Optional delivered HTML evidence

A case can declare version 1 `htmlAssertions` of type `marker-attribute`, with a unique literal
`marker`, an `attribute` name and its exact expected `equals` value. The runner then supplies new
`htmlOutput` and `htmlReport` destinations alongside the PDF destinations. These paths are selected
by the harness, never by a fixture. The Docxodus adapter calls the public standalone HTML API,
requires the same verified pinned runtime as the PDF, shares the request conversion deadline, retains its production report, and returns
`htmlArtifact: { status: "ok", sha256: "…" }`. An unavailable API, failed delivery or unverified
runtime returns `htmlArtifact: { status: "unmeasured", error: "…" }` while retaining the measured PDF.
It never converts a missing HTML observation into a PDF score of zero or a feature pass.

The harness verifies the delivered file's digest and reads its actual markup independently of
renderer diagnostics. It checks the nearest attribute across all inline fragments of one unique
marker, decodes entities, preserves the browser's first duplicate attribute, and excludes head,
script, style, template and explicitly hidden content. Attribute assertions check attributes rather than computed CSS. PDF reference eligibility and reference-engine calibration stay PDF-only.

A `marker-readable` version 1 assertion declares a unique final `marker` and the complete ordered
`tokens` of its authored paragraph. The runner supplies `htmlAssertions` and a new
`htmlObservations` destination. An optional full `htmlProfile` replaces the PDF profile for the HTML
conversion, including any omitted markup-presentation setting; both profiles are bound to the run
contract. For example, a hidden-comments PDF can have a margin-comments HTML companion.

The original observer in `bench/html_browser.mjs` opens the delivered bytes in a separate browser
context with a 1280×1024 viewport, scripts disabled, offline mode and screen media. It uses the same
verified browser executable as the production renderer, with the process sandbox enabled. It records
visible text, nearest-block text, marker ranges, ancestor clipping rectangles and overflow modes before
and after scrolling only `auto`/`scroll` ports. It also scrolls the browser viewport. It never scrolls a
`hidden`/`clip` port to manufacture access. All observation work shares the original conversion deadline.

The adapter writes raw observations, their HTML/source/executable identities and the fixed policy to
`htmlObservations`, then returns its digest as `htmlArtifact.browserFactsSha256`. The Python inspector
verifies those identities and independently derives the result from the raw facts. Passing requires an
intact ordered paragraph, one positive-sized tail range, and full containment in the final viewport and
every clipping ancestor. Content initially clipped by a non-scrollable ancestor fails. Missing evidence
is unmeasured. This checks the declared paragraph and tail access; it is not a general per-word pixel,
paint-occlusion or interactive-application fidelity test.


Version 1 `marker-computed-style` declares a unique `marker`, `property: "font-size"` and an exact
pixel value in `equals`, such as `"13.6px"`. Other properties and malformed values are rejected.
The same independent browser observer records `computedStyle`, mapping the property to the computed
values of every visible text-node fragment covered by the marker. Python requires every value to
match, in addition to a positive range fully contained in the final viewport and each clipping ancestor.
A missing observation is unmeasured; an observed size mismatch or clipped marker is a measured
failure. This does not claim to inspect every character's font across the whole document or to measure
paint occlusion. The source-bound observer, browser policy and artifact identities are unchanged.

An HTML profile may additionally declare nonempty, well-formed Unicode `additionalCss`.
The Docxodus adapter forwards it only for the HTML conversion; it never alters the PDF profile.
The full stylesheet is bound through the declared HTML profile and artifact identity. Export
versions that reject this option yield an unmeasured HTML result. For serializer regression
experiments, record explicitly when the baseline enables the API while retaining the unfixed
core serializer; do not attribute an unknown-option failure to CSS rendering.

PDF preparation also accepts `compare` with exactly two inputs and `consolidate` with a base followed
by reviewer inputs. The native adapter assigns omitted reviewer names as `Reviewer1`, `Reviewer2`, etc.
Both use the same source-bound operation build and immutable input checks as `build`.
