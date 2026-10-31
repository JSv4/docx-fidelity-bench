# Ruby annotation content and pagination

These five original Larch nursery fixtures cover centered ruby, a formatted multi-run base,
a three-page paragraph, and short/long plain-run controls for Docxodus #1483. The suite is
`core-v85` (568 PDF cases; the redline suite is unchanged).

The local diagnostic uses the native facade and a fresh browser paginator. All five candidate
cases pass their declared checks. Current main `1240cc5dc0586293cb937c59c973550027c31fda`
fails the three ruby reproductions: it loses `needle`, and its long paragraph also loses text
when the unsupported placeholder prevents fragmentation. Both plain controls have identical
complete page PNG/PPM rasters before and after.

Production public WASM export is complete at core commit
`b713506aa61efc26f03c58b4adb33d2c86fc1406`: [candidate run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41184866924)
and [current-main run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41184896314).
All five candidate mandatory checks pass. Current main cannot export the three ruby cases:
strict font validation rejects their fallback output (`resource_policy_failure`), so those
production sheets explicitly show the failure rather than a page image. The two plain controls
retain identical complete page PNGs and scores. Both LibreOffice calibrations score 100.

| Case | Production score | Close match |
|---|---:|---|
| `ruby-center` | 98.1034 | yes |
| `ruby-multiple-base` | 96.2819 | no |
| `ruby-long` | 83.9697 | no |
| `ruby-plain-control` | 99.9234 | yes |
| `ruby-long-plain-control` | 99.4276 | yes |

The multi-run mismatch includes the native centering difference below. In the long case,
all 150 nursery labels retain their native page and text, but small coordinate differences
remain: matched labels/base/guide differ by at most 0.40pt vertically and 1.73pt horizontally.
The page rasters also have a one-pixel height difference from LibreOffice's fractional page
size. These results establish restored content and pagination, not full visual equivalence.

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
claimed for the plain controls. The `*-production.png` sheets show the production run, with
explicit failure panels where main produced no PDF. `production-evidence.json` records the
artifact ZIP hashes, commit/build/runtime bindings, PDFs, calibration, checks, page rasters and
screenshots. Word's native capture stays outside the source tree; its input/PDF hashes and
observations are recorded in the local evidence metadata.
