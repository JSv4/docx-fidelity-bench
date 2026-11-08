# Small minimum line spacing

Four original Primrose documents isolate the confirmed 13pt minimum on uniform
10pt Liberation Serif text from [Docxodus #1566](https://github.com/JSv4/Docxodus/issues/1566).
They contain literal OOXML and original labels; no product fixture, helper or font
program is imported. Inputs and metric checks were frozen before candidate capture.

| Case | Authored spacing | Lines | Lines per page |
| --- | --- | ---: | --- |
| short | 13pt minimum | 18 | 18 |
| continued | 13pt minimum | 64 | 49 / 15 |
| natural-control | Single spacing | 18 | 18 |
| sixteen-control | 16pt minimum | 18 | 18 |

Every label has an independently derived advance of `10467 / 2048 × 10` points.
The `x` between its digits avoids the font's special adjacent-digit kerning. A 60pt
column fits exactly one label per line. The independently provisioned font has
1825 ascent units, −443 descent units and an 87-unit line gap: natural pitch is
`2355 / 2048 × 10` points, while the PDF glyph box is `2268 / 2048 × 10` points high.
The authored 13pt minimum gives `floor(648 / 13) = 49` complete lines per page.

The [issue author's Word print](https://github.com/JSv4/Docxodus/issues/1566#issuecomment-6701329387)
confirms the 13pt pitch. The [ECMA remarks in the Open XML SDK documentation](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.spacingbetweenlines.line?view=openxml-3.0.1)
describe centered text when a minimum is larger than its natural line. These cases
use complete line slots rather than assigning unmeasured Word first-baseline coordinates.
They do not claim mixed-font line metrics or a new Word capture.

Each label has an authored page and line-slot assertion with a 0.5pt position bound.
`MinimumChecks.py` also checks glyph width and height within 0.1pt, adjacent pitch,
and cumulative displacement from the first label on each page within 0.75pt. The
latter bound accounts for independently rounded PDF origins without permitting
small errors to accumulate down a page. Exact inventory, content-stream order,
visible ink, physical page geometry and total page count are required.
The checker validates the plain source scaffold, including defaults and absence
of direct formatting overrides. Synthetic probes prove that glyph shrinkage can
pass containment while failing metric checks, and gradual drift can pass adjacent
pitch checks while failing cumulative checks.

`Compose.py` binds inputs, exact renderer builds, all runtime assets, exported
HTML/PDFs and production reports. These are strict-font public-API diagnostic
exports through sandboxed system Chromium, compared with separately provisioned
LibreOffice 25.8.7.3. Native eligibility is measured against the same authored
contract; there is no whole-suite score or pinned-browser qualification.
Both unchanged controls must retain identical baseline/candidate text geometry
and page rasters. Each labeled sheet includes every page from all three renderers.

The baseline passes both controls and fails the two 13pt cases. LibreOffice passes
the two 13pt cases and the 16pt control. Its natural control has eight line-slot
failures and three cumulative-pitch failures; these remain explicit native
diagnostics and do not change the frozen acceptance bounds.

All four candidate cases pass. All twelve PDFs retain all 354 observed source
tokens across fifteen pages, and all 47 damaged observations are rejected.
The two controls are raster-identical between baseline and candidate.
During evidence assembly, missing wrong-page distances in baseline records used
non-finite values that did not compare equal after JSON reload. These now use
`null`; the acceptance predicate and all twelve PDFs' pass/fail decisions are
unchanged. The original verifier/freeze and the equivalence proof are retained in
`serialization-diagnostic/`. No input, geometric expectation or tolerance changed.

Reproduce with the four-case manifest, the exact commits in `evidence.json`,
`docs/results/export-reliability/Capture.mjs`, then `Compose.py RUN BASELINE CANDIDATE`
and `Mutations.py`. The retained evidence records source/build/artifact hashes,
schema validation, measurements and all comparison sheets.
