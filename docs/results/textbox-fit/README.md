# Effective textbox fit at the paper edge

Twelve original Linden fixtures cover omitted fit, explicit fixed fit, text/line/shape theme
defaults, an empty theme, local precedence, headers and footers. Three on-page controls cover
default, growing and shrinking fit. All packages validate with Open XML SDK 3.5.1. `core-v92`
contains 645 cases; the preceding 633 inputs and contracts are unchanged except the generator hash.

The edge cases use a box at x=84pt, y=748pt with a 180pt by 96pt extent. Three labeled lines
remain on Letter paper, while an empty deleted paragraph's markup is wholly off paper. The two
explicit-fixed controls retain that exact content and placement. The three on-page controls
use y=60pt and an ordinary empty paragraph: LibreOffice omits a deleted paragraph's generated
mark even in markup output, whereas Docxodus displays it. No token exception is added for that
renderer difference. Public renderer tests separately retain on-page tracked-mark coverage.

| Cases | Main | Fixed | LibreOffice 25.8.7.3 |
| --- | --- | --- | --- |
| Omitted local fit; absent, empty, text, line or shape defaults | Five refusals | Complete | Complete |
| Header default and footer text default | Two refusals | Complete | Complete |
| Explicit fixed and local-over-theme controls | Complete | Identical page rasters | Complete |
| Three on-page controls | Complete | Identical page rasters | Complete |

Main is `72319002a6286d09d68eb5b555434f35fc435945`, captured with the identical source tree
and runtime from `0875eab87ecaf0af716af7c585f9745d159c4a95`. The fixed source is
`5fe5cbcd644a925799db0e9eb474860b0039122d`. All twelve candidate PDFs pass complete token
inventories, declared-font checks, physical geometry and visible-label bounds. All twelve native
references are eligible. All five control page PNGs are byte-identical between main and fixed.

These local diagnostics use strict fonts, explicit Liberation Serif files and caller-owned,
sandboxed Chromium 143.0.7499.4; reports identify the runtime as `browserObserved`.
Production owned-process measurements are pending. This demonstrates completeness and correct
refusal behavior, not exact native layout parity. No fresh Word reference is claimed.

[Input, PDF, report, runtime and screenshot bindings](local-evidence.json) record every check.
[SDK validation](source-sdk-validation.json) binds each package hash to its findings. Every
sheet shows all actual PDF pages at 96 DPI and 100%, without cropping or resampling. There are
29 actual page panels and seven explicitly labeled export refusals.

![Default fit at edge](textbox-fit-edge-default.png)

![Explicit fixed control](textbox-fit-edge-explicit-control.png)

![On-page default control](textbox-fit-onpage-default-control.png)

![Text default](textbox-fit-edge-text-default.png)

![Line default](textbox-fit-edge-line-default.png)

![Shape default](textbox-fit-edge-shape-default.png)

![Empty theme](textbox-fit-edge-empty-theme.png)

![Local fit overrides theme control](textbox-fit-edge-local-over-theme-control.png)

![Header default](textbox-fit-header-edge-default.png)

![Footer text default](textbox-fit-footer-edge-text-default.png)

![On-page growing fit control](textbox-fit-onpage-text-auto-control.png)

![On-page shrinking fit control](textbox-fit-onpage-text-shrink-control.png)
