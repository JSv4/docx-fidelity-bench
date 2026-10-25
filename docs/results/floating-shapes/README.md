# Floating-shape captures

These eleven original cases reproduce missing DrawingML shape/group ink and text clearance,
with no-wrap, mixed-text and inline-drawing controls. They also cover behind-text paint order,
large unsigned stacking values, explicit square/tight/through wrapping, a preset hexagon and a
plain VML rectangle. `bench/fixtures.py` authors all text and geometry; no product fixtures,
third-party graphics or font files are imported. All 943 previously tracked DOCX files retain
their original bytes.

All eleven sheets were visually inspected. Each sheet shows full-page, 96-dpi PDF rasters: LibreOffice 25.8.7.3, Docxodus before the fix
(tree identical to main a1a07d36), and the source-bound fixed renderer. Nothing is cropped or
aligned. The floating shapes disappear before the fix. Afterwards, top/bottom wrapping keeps
its clearance, no-wrap retains ordinary text flow, background ink stays above the paper and
below text, and the hexagon and VML rectangle draw without inserting placeholder labels.

Local Docxodus exports use a caller-owned Chromium browser because this host cannot establish
its process sandbox. They pass strict font policy, but remain **unmeasured for production
scoring**. The adapter eligibility checks and committed sandboxed export tests are unchanged.
`capture.json` records source/build/browser identities, input and PDF/report/sheet hashes,
text inventories and observed marker positions. These observations are diagnostic evidence,
not a complete candidate score.

All eleven LibreOffice references meet their declared checks. An independent repeat export
calibrates at 100 for these eleven cases. Coverage is explicitly partial: 11 of 302 PDF cases.
No full-suite score is claimed.

Office Online and Word document control were unavailable. Two variants remain pending Word
adjudication: LibreOffice puts the later orange drawing above the teal drawing when their
unsigned `relativeHeight` values are 2147483648 and 4294967295 respectively; Docxodus preserves
numeric order. LibreOffice also uses rectangular clearance for the filled rectangle's supplied
triangular tight/through contour, while Docxodus uses that contour. The sheets retain these
visible differences. Neither renderer is claimed as a verified Word reference for those variants.

The SDK 3.5.1 validator reports no findings for the eleven inputs. The full visible-text inventory
and existing mandatory PDF checks remain in force. Region assertions also pin the following
paragraph below top/bottom shapes and beside edge-wrapped shapes, so missing exclusions cannot
pass merely by retaining the text.

## Sheets

- [drawings-floating-shape-top-bottom](drawings-floating-shape-top-bottom.png)
- [drawings-floating-group-top-bottom](drawings-floating-group-top-bottom.png)
- [drawings-floating-shape-mixed-top-bottom](drawings-floating-shape-mixed-top-bottom.png)
- [drawings-floating-shape-no-wrap-control](drawings-floating-shape-no-wrap-control.png)
- [drawings-floating-shape-behind-text](drawings-floating-shape-behind-text.png)
- [drawings-floating-shape-relative-height](drawings-floating-shape-relative-height.png)
- [drawings-floating-shape-square](drawings-floating-shape-square.png)
- [drawings-floating-shape-tight](drawings-floating-shape-tight.png)
- [drawings-floating-shape-through](drawings-floating-shape-through.png)
- [drawings-floating-shape-unsupported](drawings-floating-shape-unsupported.png)
- [drawings-floating-vml-plain](drawings-floating-vml-plain.png)
