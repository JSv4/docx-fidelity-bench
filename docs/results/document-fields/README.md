# Document properties and running style fields

These seven original cases cover [Docxodus #1481](https://github.com/JSv4/Docxodus/issues/1481).
They are authored by `bench/fixtures.py`, use separately installed Liberation Serif, and contain
no imported document, image or font program. Simple and complex field syntax appear in body,
header and footer stories. The complete visible-token inventory remains mandatory.

Production exports at main `1240cc5` and candidate `8a0a2e91` use the public WASM export path
and pinned Chromium 143.0.7499.4, compared with LibreOffice 25.8.7.3. The
[candidate run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41177630479) and
[main run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41177656533) retain the raw
PDFs, rasters, calibration and export reports. [production-evidence.json](production-evidence.json)
binds their input, renderer, output and artifact hashes. Both reference calibrations score 100
and pass every mandatory check. No fresh Word rendering is claimed.

| Case / full-page screenshot | Main | Candidate |
|---|---|---|
| [Uncached properties](fields-property-uncached-production.png) | Six title/property results absent | All six values and story-region checks pass |
| [Cached property control](fields-property-cached-control-production.png) | Pass | Pass; page pixels unchanged |
| [Uncached running styles](fields-styleref-uncached-production.png) | Running headings absent | ALDER then BIRCH in header and footer |
| [Stale running cache](fields-styleref-stale-cache-production.png) | Page two repeats ALDER | Page two uses BIRCH |
| [Constant heading control](fields-styleref-constant-control-production.png) | Pass | Pass; both page rasters unchanged |
| [Wrapping running heading](fields-styleref-wrapping-production.png) | Two pages under a stale short header | Three pages; body tail follows the expanded header band |
| [Constant wrapping control](fields-styleref-wrapping-control-production.png) | Pass | Pass; all three page rasters unchanged |

Every candidate passes all declared PDF checks against the native reference. Each control's
complete decoded page pixels and deterministic PNG bytes match main. This is raster identity,
not PDF-byte or HTML-metadata identity. All screenshots show complete pages at 75% of their
96 DPI raster size, including the smaller 228 by 240 pt wrapping pair.

Production visual scores are 97.212 for the property pair, 95.819 for the three short-heading
cases, and 85.935 for the wrapping pair. The wrapping control has the same score on main:
existing differences in bold heading spacing remain visible beside LibreOffice. Passing the
mandatory content, geometry and page-ownership checks does not claim exact native visual parity.

Earlier native-facade/browser diagnostics remain in [local-evidence.json](local-evidence.json)
and the seven images without the `-production` suffix. Their exact assemblies embed the recorded
source revisions; they are separate evidence from the production exports above.

The harness deliberately requires unique marker tokens. Adjacent PAGE fields label repeated
running copies (`Running2:BIRCH`, for example), so absolute header/footer regions can check
physical page ownership without changing that rule. The wrapping case additionally requires
`JuniperWrapTail` on page three below the enlarged header. Independent review demonstrated
that the initial short-heading cases could pass a text-only substitution after pagination;
the wrapping pair was added to make missing reflow observable.

Locked fields are covered by renderer tests and separate local diagnostic fixtures. LibreOffice
updates the locked STYLEREF cache in those probes, so it is not used as a parity oracle for locks.
