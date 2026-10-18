# Renderer adapter protocol

Protocol version 1 uses one JSON request on stdin and one JSON response on stdout. The runner invokes an explicit command vector without a shell. Fixture records cannot select executable commands. Add adapter selection in `bench/__main__.py`; metrics and fixture IDs stay unchanged.

The request contains `protocol`, absolute `input` and `output` paths, `inputSha256`, a production `report` destination, an explicit `profile` (`review`, `comments`, optional `markupPresentation`), `fontDirectories`, exact `candidate` identity, and `timeoutMs`. `markupPresentation: "word"` selects Word-style tracked-change appearance for a markup review profile; omitting it retains the renderer default. The input is immutable. Output paths are new and must not be overwritten. The renderer must use the declared fonts and view.

An `ok` response contains `protocol: 1`, `status: "ok"`, `pdfSha256`, and `renderer` identity. Candidate PDF bytes must exist at the requested path and match the digest. Include candidate source/build identity and runtime identity. The Docxodus adapter retains a complete production report and source-bound build record.

A known conversion or unsupported-feature failure returns `status: "failed"` and structured `error`; the case scores zero. An unavailable host, unverifiable build, or unsuitable capture environment returns `status: "unmeasured"` and the reason; complete coverage is blocked. The runner independently reads the produced PDF and scores it. Internal layout metadata cannot substitute for that evidence.

`bench build-docxodus` builds only production WASM/TypeScript and public export assets, then writes `.docx-bench-build.json` in the separately provisioned renderer checkout. The adapter checks source commit/tree, clean tracked files, Node version, module path, build recipe, lockfiles, and build artifact hashes. It checks the supported sandboxed export runtime and configured fonts. It does not run renderer test suites or import their fixtures.

## Redline adapters

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
script, style, template and explicitly hidden content. It checks attributes, not computed CSS or
interactive behavior. PDF reference eligibility and reference-engine calibration stay PDF-only.
