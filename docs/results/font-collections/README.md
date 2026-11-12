# Collection fonts

Four original Liatris documents cover collection discovery in
[Docxodus #1573](https://github.com/JSv4/Docxodus/issues/1573). Each TTC/OTC-only
family has a standalone-font control. A pair differs only in its requested family;
the text, package parts and paragraph metrics are identical. All 1,062 previous
DOCX input hashes are unchanged in `core-v148` (1,066 cases).

The three small font programs in `fixtures/collection-fonts` are authored by
`bench/collection_fonts.py` using only Python's standard library. Every visible
glyph is an original chevron, with character-dependent advances. Selectable text,
physical font identity and marker positions are checked independently of those
deliberately simple outlines. No installed or product-test font was copied. The
fonts and generator are MIT-licensed; regeneration and provenance checks bind the
exact bytes. DOCX packages contain no embedded font programs. Both benchmark
collections contain TrueType outlines; product tests also exercise a mixed
TrueType/CFF OpenType collection.

All four LibreOffice 25.8.7.3 captures are eligible, and reference calibration scores
100 with every mandatory check passing. The [capture manifest](capture-manifest.json)
and [reference bundle](reference-bundle.json) bind inputs, PDF hashes, font names,
environment and inspections. All four documents have
[zero Open XML schema findings](schema-validation.json). Full token inventories,
required font families and first/last marker positions remain mandatory; no score,
tolerance or font-verification policy was changed.

The production comparison uses exact source builds of main
`a2e70ffb6f490730c8418187c02f69ccbbeae64c` and fixed
`323876893b5c461dda78b4c4470b31844522c0e4`, through the public export API and pinned
Chromium 143.0.7499.4. Both use the same eligible native reference bundle and
strict font verification. Main cannot resolve either collection-only family and
produces no PDF; the standalone controls pass.

| Case / full-page comparison | Main | Fixed |
|---|---:|---:|
| [TTC-only family](font-collection-ttc-requested-comparison.png) | 0; export rejected | 99.685; all checks pass |
| [TTC standalone control](font-collection-ttc-standalone-control-comparison.png) | 99.685 | 99.685; pixels unchanged |
| [OTC-only family](font-collection-otc-requested-comparison.png) | 0; export rejected | 99.686; all checks pass |
| [OTC standalone control](font-collection-otc-standalone-control-comparison.png) | 99.686 | 99.686; pixels unchanged |

The four-case mean increases from 49.843 to 99.685; mandatory pass rate increases
from 2/4 to 4/4. Small raster differences from LibreOffice remain. Both controls'
complete page PNGs are byte-identical between main and fixed. The
[production evidence](production-evidence.json) hashes every retained PDF, raster,
report, build identity and run result. Comparison sheets show complete pages;
failure panels explicitly label the absence of a baseline PDF.

These cases measure collection discovery through explicit directories. Product
tests cover the opt-in OS index, lazy loading, precedence, rights, retries,
cancellation and default-off output identity. No Word capture or Word typography
parity is claimed, and this four-case result is not a full-corpus score.

To reproduce, create a private fontconfig file that includes `/etc/fonts/fonts.conf`,
adds the absolute `fixtures/collection-fonts` directory, and uses an ignored cache
directory. Export its path as `FONTCONFIG_FILE` for native capture and both runs;
this provisions the original font programs without installing them globally.
Build each clean checkout with `python3 -m bench build-docxodus --source SOURCE
--commit FULL_SHA`. Use the retained capture manifest with `bench reference` and
`bench run`, setting `DOCXODUS_SOURCE_ROOT` and `DOCXODUS_EXPORT_MODULE` to that
checkout and its `npm-export/dist/index.js`. The adapter's strict font, runtime
identity and source-build checks stay enabled.
