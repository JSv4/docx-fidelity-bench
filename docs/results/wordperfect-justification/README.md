# WordPerfect justification: independent diagnostic cases

Four original Tansy documents exercise the explicit `w:wpJustification` option.
They were authored here with literal OOXML and a separately provisioned Liberation
Mono font. No Docxodus fixture, helper, document, or font program is imported.
The source inputs and expectations were frozen before candidate capture.

The [Microsoft implementation note](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/faeffa01-a15f-4e62-b63c-023901149d29)
and [Open XML SDK remarks](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.wordperfectjustification?view=openxml-3.0.1)
define the rule: select words using `actualWidth * (1 + 281/7200)`, then reduce
interword spacing to fit the actual line. This is independent of compatibility
mode. First-line indentation reduces actual width before expansion. The
[issue author's Word observation](https://github.com/JSv4/Docxodus/issues/1550#issuecomment-6701327696)
confirms the original 66-character mode-14 example; this artifact does not add a
Word capture or claim to settle extreme condensation or modern mixed-run layout.

| Case | Authored behavior |
| --- | --- |
| control | Mode 14 with the flag explicitly disabled; ordinary line selection. |
| mode14 | Enabled flag, 66 characters within the expanded budget, 68 beyond it, and a 36pt first-line indent. |
| mode15 | The same enabled rule and boundary/indent inputs in mode 15. |
| continued | 300 unique labels, six per line across 50 lines and two pages. |

At 12pt, independently provisioned Liberation Mono advances each character by
`1229/2048 * 12` points and has a `2320/2048 * 12` point line metric. Every source
word has an authored page/rectangle with a 0.5pt print-position bound. The scoped
`WidthChecks.py` additionally requires each word's natural width and height within
0.1pt. This rejects glyph scaling even when smaller text remains inside the
correct containment rectangle. Complete ordered inventory, physical pages, and
dark painted source text are checked independently. Content-stream order comes
from `pdftotext -raw` on the same PDF; bbox words retain their unchanged geometric
checks. Before candidate capture, both baseline and native control showed that
`-bbox-layout` groups wide justified gaps into apparent columns. The initial
diagnostic and all eight successful raw-order probes are retained under
`pre-capture-order/`; no geometric tolerance or source expectation changed.

`Compose.py` binds retained PDFs/reports to frozen inputs, exact renderer source
and build identities, and every exported runtime asset. `Mutations.py` damages
copies of observations, including uniformly shrinking glyphs without moving their
left positions or changing line selection. The tests also prove that the older
containment checks alone accept that damage and the scoped metric check rejects it.

These are unscored strict-font public-API exports through sandboxed system
Chromium, compared with separately provisioned LibreOffice 25.8.7.3. The native
reference is eligible only where it satisfies the authored assertions. There is
no new Word reference, pinned-browser qualification, or whole-suite score.
Every labeled comparison sheet includes every page from all three renderers.

The candidate passes all four authored cases; baseline and LibreOffice each pass
the disabled control and mode-15 case. The two mode-14 differences remain explicit
failures in the native comparison. All twelve PDFs retain all source words
(1,116 observed tokens across fifteen pages), and all 43 corrupted observations
are rejected. The disabled control is raster-identical before and after the fix.

Measured results and artifact hashes are recorded in [evidence.json](evidence.json).
