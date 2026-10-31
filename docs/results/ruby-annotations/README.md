# Ruby annotation content and pagination

These five original Larch nursery fixtures cover centered ruby, a formatted multi-run base,
a three-page paragraph, and short/long plain-run controls for Docxodus #1483. The suite is
`core-v85` (568 PDF cases; the redline suite is unchanged).

The local diagnostic uses the native facade and a fresh browser paginator. All five candidate
cases pass their declared checks. Current main `1240cc5dc0586293cb937c59c973550027c31fda`
fails the three ruby reproductions: it loses `needle`, and its long paragraph also loses text
when the unsupported placeholder prevents fragmentation. Both plain controls have identical
complete page PNG/PPM rasters before and after. Production public-export capture is pending.

| Case | Purpose | Native geometry contract |
|---|---|---|
| `ruby-center` | Both layers and the centered guide | Base and guide bounds within 1.25pt of LibreOffice |
| `ruby-multiple-base` | Bold/plain base runs remain together | Base bounds within 1.25pt; guide y-band29–38pt, with x spanning the documented native/candidate positions |
| `ruby-long` | All 150 labels and the pair survive continuation | Complete token inventory; base and guide bounds within1.25pt |
| `ruby-plain-control` | Short no-ruby control | Complete inventory; both words share their page |
| `ruby-long-plain-control` | Long no-ruby control | Complete inventory; both words share their page |

LibreOffice 25.8.7.3 is a diagnostic reference. It ignores `hps` without an explicit guide run
size and drops all but the last guide run, so these fixtures use an explicit 6pt guide. Core
public-export tests separately cover multi-run guides and conflicting/omitted size declarations.
LibreOffice also puts the guide at the first base run's left edge in the multi-run case. Word
for the web centers it over the combined base, as Docxodus does: guide center115.30pt versus
base center115.18pt in the independently captured original input. Word substituted Times New
Roman for requested Liberation Serif; this verifies the behavior and is not a font-matched
Word oracle. The multi-run guide's x-position is deliberately outside the LibreOffice geometry
contract; the centered single-run case retains the stricter guide check.

The five labeled sheets show every page from LibreOffice, main, and the candidate at 75% of
96 DPI raster size. `local-evidence.json` binds the inputs, native DLLs, browser bundles,
PDF/HTML hashes, every page raster and the screenshots. No PDF-byte or HTML-byte identity is
claimed for the plain controls. Word's native capture stays outside the source tree; its
input/PDF hashes and observations are recorded in the evidence metadata.
