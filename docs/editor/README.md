# Editor browser diagnostic v1

This unweighted diagnostic exercises the shipped `mountRibbon` and `DocxEditor` surface.
It is separate from the PDF and redline metrics. It does not claim Word layout parity or
satisfy the standalone PDF export's browser-sandbox eligibility contract.

Ten original inputs form five reproducer/control pairs: empty move/custom-XML review counts,
unanchored revision lookup, ArrowRight across a tab, and actual plain/rich clipboard copy
with inline or class-based formatting. `bench/editor_fixtures.py` authors the complete OOXML,
Cedar text, identities, expected text and native carrier counts. No product fixtures, test
harness, private editor state, imported document, or generation helper is copied in.

The lookup case calls the public `revisionAt` on a detached copy of the actual rendered mark,
then accepts that entry through the public API. The saved OOXML must have accepted the real
insertion while preserving the unrelated empty markers. This deliberately tests the API's
no-anchor fallback rather than pretending the ordinary mounted paragraph has no anchor.

The copy cases use real Ctrl+C and Ctrl+V into independent textarea and editable rich-text
targets. The rich target lives in a neutral iframe document so source stylesheets cannot
make class-only clipboard HTML appear correctly formatted. They do not inject clipboard events or use a renderer text reader as the oracle.
The caret case types X after one ArrowRight, saves, and checks actual `w:t`/`w:tab` carriers.
A literal tab in text cannot satisfy the native-tab assertion. The external Open XML SDK
validator must report zero findings for all original inputs and saved outputs.

Every run binds exact clean renderer source, the production build receipt and runtime asset
hashes, the additional ribbon build command/bundle hash, browser version/executable hash,
input manifest, action scripts, saved DOCX and labeled screenshot hashes. All declarations
and input hashes are checked before and after the run. Unsupported browser/runtime actions
remain unmeasured; the summary is complete only when all ten actions are observed and every
control passes. Individual failures remain visible. There is no weighted score.

Provision .NET 10, the WASM workload, Node and Chromium as described in the main README.
Build the external renderer and the independent validator, then run:

```sh
python3 -m bench build-docxodus --source /path/to/Docxodus --commit FULL_SHA
python3 -m bench redline build-validator --out runs/editor-validator
python3 -m bench.editor --source /path/to/Docxodus --commit FULL_SHA \
  --output runs/editor-ui/candidate --validator runs/editor-validator
```

Use a new output directory each time. Run outputs are ignored. The runner additionally builds
`npm run build:editor-bundle` from the same clean source; it does not load the product's test
harness or alter the renderer's implementation. Install that source's pinned Playwright
Chromium before running. The diagnostic uses Linux Ctrl+C/Ctrl+V chords.
