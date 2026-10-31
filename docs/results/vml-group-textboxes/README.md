# Independent VML textbox stories

Paired with [Docxodus #1482](https://github.com/JSv4/Docxodus/issues/1482) and
[core PR #1499](https://github.com/JSv4/Docxodus/pull/1499).
Six original Maple fixtures cover body/header groups, nested groups, and separate-box controls.
All packages pass Open XML SDK 3.5.1 validation. Both labels have mandatory page-one region
assertions, as well as exact visible-token counts. Grouped/nested labels additionally must be
within 0.75 pt of native reference positions. A mutation with the second label at the first
label's position fails even though its token counts match. Independent review also found that
the broad regions accepted an ignored nested origin; the added native-position checks reject
that actual browser mutation, including either axis independently.

Local diagnostics use native converter assemblies and fresh pagination bundles at main
`1240cc5dc0586293cb937c59c973550027c31fda` and candidate
`0d5655f328d22c043b1aa6db6ea7471271ff1909`, plus LibreOffice 25.8.7.3.
These captures are not production standalone exports. Production measurements are pending;
no fresh Word reference is claimed. [The report](local-evidence.json) binds inputs, libraries,
bundles, PDFs, raster pages, checks, schema findings, scripts, installed fonts and screenshots.

| Case | Main | Candidate and LibreOffice |
|---|---|---|
| [textboxes-vml-body-group](textboxes-vml-body-group.png) | Second label absent; first label misplaced | All mandatory checks pass |
| [textboxes-vml-body-nested](textboxes-vml-body-nested.png) | Second label absent; first label misplaced | All mandatory checks pass |
| [textboxes-vml-body-separate-control](textboxes-vml-body-separate-control.png) | Pass; complete raster unchanged | All mandatory checks pass |
| [textboxes-vml-header-group](textboxes-vml-header-group.png) | Second label absent; first label misplaced | All mandatory checks pass |
| [textboxes-vml-header-nested](textboxes-vml-header-nested.png) | Second label absent; first label misplaced | All mandatory checks pass |
| [textboxes-vml-header-separate-control](textboxes-vml-header-separate-control.png) | Pass; complete raster unchanged | All mandatory checks pass |

The two separate-box controls retain byte-identical complete main/candidate page rasters.
LibreOffice applies a roughly 4.4 pt text inset to separate boxes despite their zero-inset
markup; this existing native difference remains visible and is allowed by the position regions.
The grouped/nested candidate labels match the native positions. The groups map a 600 × 300
coordinate space at origin (20, 40) into a 288 × 144 pt frame. Child fonts remain physical sizes.

Every sheet shows full pages at 75% of the 96-DPI page rasters, with explicit provider labels.
The fixtures import no renderer helper, document content, image or font program.
