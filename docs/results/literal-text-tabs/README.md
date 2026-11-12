# Literal-text tab captures

These eleven original cases cover body, header, footer and consecutive tabs with paired
explicit-tab controls. Three more cases cover deleted literal text, deleted explicit tabs
and an untracked explicit-tab control. Labels, formatting and complete token inventories
are authored in this repository. The right stop is 9,360 twips; the consecutive-tab pair
also has a left stop at 2,400 twips.

The sheets compare actual LibreOffice reference PDFs with Docxodus PDFs before and after
[the implementation change](https://github.com/JSv4/Docxodus/pull/1362).
They retain the full horizontal page extent; footer sheets crop the bottom 216 pixels,
and other sheets show the top 320 pixels, at 96 dpi. These presentation crops do not
change scoring inputs, alignment, full-page raster measurements or token checks.

The local host cannot establish Chromium's process sandbox. Docxodus captures use a
caller-owned diagnostic browser with `browserObserved` verification and are **unmeasured
for production scoring**. The before renderer's body, consecutive-tab and deleted-literal
cases fail strict font glyph coverage on the raw tab character. Only these three before
captures retry without strict fonts for visual inspection; their original strict failure
reports and hashes are retained. Every after capture passes strict font policy. The
benchmark adapter and the implementation's committed sandboxed export tests retain their
production policies.

All eleven LibreOffice reference-provider calibration cases score 100, with full token
inventories and isolated-dot-leader normalization. This is capture calibration, not a
Docxodus candidate score. The focused reference bundle covers eleven of 286 required PDF
cases, so no complete-suite score is claimed. No new Word capture is claimed.

`capture.json` records source-bound build identities, source revisions, input/PDF/raster
hashes, crop dimensions, SDK validation, strict font outcomes and the focused calibration
contract. All eleven final sheets were visually inspected. Review caught revision strikethrough
being lost at an inline flex boundary; the final capture uses the corrected renderer and
retains the strike while placing the marker at its stop.
