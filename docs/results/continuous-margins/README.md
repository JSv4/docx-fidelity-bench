# Continuous section margins

Twelve original Hemlock documents reproduce Docxodus #1486 and pair each margin change with
unchanged-margin and explicit-page controls. The suite is `core-v87` / 590 cases. All 578 prior
input bytes and contracts remain unchanged except their generator digest.

| Cases | Observable behavior |
|---|---|
| Left/right, short and spilling | The new text column starts on the existing page; left and right edge labels expose both placement and available width |
| Top/bottom, short and spilling | The shared page keeps its original vertical band; later body pages adopt the new margins |
| Same-margin short/spill controls | Existing one-page and three-page flow remains unchanged |
| Explicit next-page control | Equal-sized sections still start separate pages |
| Changed-paper next-page control | An explicit page boundary also preserves different physical page widths |

Each line is exactly 12 pt high and contains one short label. The 120-line spills distinguish
the old 54-line first page from a later 48-line page when its top or bottom margin increases.
The first section contains one additional opening line. Right-aligned labels on every spill
page expose incorrect retained widths even when a short left-aligned word would not wrap.
The paper control deliberately uses `nextPage`; the core public tests separately cover a
continuous paper-size change, where Word and LibreOffice differ.

Horizontal bounds use the declared 11 pt Liberation Serif glyph advances read independently
from its `hmtx` table, plus 0.75 pt at each edge. The units and font hash are recorded in
`local-evidence.json`. Vertical bounds cover each exact line's glyph box. No candidate output
supplies the expected bounds. Fresh Word for the web captures establish immediate horizontal
geometry and delayed vertical geometry. Word substitutes Times New Roman, so those captures
are behavior diagnostics, not registered font-matched page references.

The margin assertions are Word-adjudicated. They bind every candidate; the existing provider
rule excludes them only from LibreOffice reference eligibility/calibration. LibreOffice's raw
results remain recorded. It retains old horizontal geometry on a shared page and differs on
later vertical geometry. Full-page scores still expose these disagreements; mandatory success
does not establish complete visual equivalence.

Local candidate means across each case's pages range from 11.1127 to 99.9934. Six cases
do not meet the close-match criteria: both short horizontal changes and all four changed-margin
spills. The left spill has the lowest score because LibreOffice retains x72 while Word and
the candidate use x144. The controls and the short top/bottom cases meet those criteria.
These local means are diagnostic; production scoring is reported separately below when ready.

The final local native-facade/Chromium diagnostic passes all twelve candidate cases. Main
`1240cc5dc0586293cb937c59c973550027c31fda` fails all eight margin reproducers and passes four
controls. All eight control pages have identical main/candidate rasters and scores. The
candidate TypeScript is `763314857e5fa0ede6efac41630fa941de835058`; its unchanged native converter
is the validated parent `0cb9566acf63ccaf1c0ebf16fea81b84a63342f4`. Public production exports are
pending and will be recorded separately.

An independent adversarial reviewer found two false passes in the initial assertions: broad
regions allowed a 24 pt shift, and left-edge-only content did not observe an incorrect column
width. The final edge labels and font-derived bounds reject all six actual mutated PDFs.
The reviewer separately verified all twelve positive cases, four control pixel identities,
source token inventories, font advances and unchanged prior fixtures. No fixture or contract
findings remain.

Every labeled sheet shows complete 96 DPI pages at 50% display scale, with renderer and page
labels outside the page area. Blank cells indicate that renderer has no corresponding page.
The metadata binds the inputs, PDFs, HTML, rasters, screenshots, tools, fonts and Word captures.
No PDF-byte or HTML-byte equivalence is claimed for controls. Native PDFs remain outside the
source inventory; no external document content, font program or authentication data is included.
