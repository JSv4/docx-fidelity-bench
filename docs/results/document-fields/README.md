# Document properties and running style fields

These seven original cases cover [Docxodus #1481](https://github.com/JSv4/Docxodus/issues/1481).
They are authored by `bench/fixtures.py`, use separately installed Liberation Serif, and contain
no imported document, image or font program. Simple and complex field syntax appear in body,
header and footer stories. The complete visible-token inventory remains mandatory.

Local diagnostics use native Docxodus conversion plus the browser paginator at main `1240cc5`
and candidate `8a0a2e91`, compared with LibreOffice 25.8.7.3. Exact assembly, bundle, input, PDF,
raster and screenshot hashes are in [local-evidence.json](local-evidence.json). Both native
assemblies embed their recorded source revision. These are not production AOT export results;
production measurement is pending. No fresh Word rendering is claimed.

| Case / full-page screenshot | Main | Candidate |
|---|---|---|
| [Uncached properties](fields-property-uncached.png) | Six title/property results absent | All six values and story-region checks pass |
| [Cached property control](fields-property-cached-control.png) | Pass | Pass; page pixels unchanged |
| [Uncached running styles](fields-styleref-uncached.png) | Running headings absent | ALDER then BIRCH in header and footer |
| [Stale running cache](fields-styleref-stale-cache.png) | Page two repeats ALDER | Page two uses BIRCH |
| [Constant heading control](fields-styleref-constant-control.png) | Pass | Pass; both page rasters unchanged |
| [Wrapping running heading](fields-styleref-wrapping.png) | Two pages under a stale short header | Three pages; body tail follows the expanded header band |
| [Constant wrapping control](fields-styleref-wrapping-control.png) | Pass | Pass; all three page rasters unchanged |

Every candidate passes all declared PDF checks against the native reference. Each control's
complete decoded page pixels and deterministic PNG bytes match main. This is raster identity,
not PDF-byte or HTML-metadata identity. All screenshots show complete pages at 75% of their
96 DPI raster size, including the smaller 228 by 240 pt wrapping pair.

The harness deliberately requires unique marker tokens. Adjacent PAGE fields label repeated
running copies (`Running2:BIRCH`, for example), so absolute header/footer regions can check
physical page ownership without changing that rule. The wrapping case additionally requires
`JuniperWrapTail` on page three below the enlarged header. Independent review demonstrated
that the initial short-heading cases could pass a text-only substitution after pagination;
the wrapping pair was added to make missing reflow observable.

Locked fields are covered by renderer tests and separate local diagnostic fixtures. LibreOffice
updates the locked STYLEREF cache in those probes, so it is not used as a parity oracle for locks.
