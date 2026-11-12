# Manual text widths

Six original documents exercise a natural-width control, 20pt and 100pt single-run
regions, differently styled runs sharing 100pt, separate IDs each receiving 100pt,
and one 100pt region inside a paragraph continued over two pages. Juniper is the
fitted word; Ledger and every Fern label retain their ordinary font advances.

The oracle is the authored `w:fitText` width and the separately installed Liberation
Mono font program: 1229/2048 em per character, 2320/2048 em natural height, at 12pt.
Glyph bounds must match within 0.1pt; source-derived page/line positions have 0.5pt
allowance. Ordered inventories, paint and paper geometry are also checked.
Microsoft documents that contiguous runs with the same ID share one target width:
[fitText](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/aec27882-4aa1-491c-9c00-fbc9bb00c9f7).

Inputs, source assertions and the strict width verifier were frozen before candidate
capture. LibreOffice 25.8 ignores fitText: only the natural-width control qualifies
as a reference. Its five fitted outputs are retained and labeled ineligible.
These are diagnostic exports through the public API with verified fonts and a
sandboxed system Chromium; they are not a benchmark score or new Word parity claim.

`evidence.json` binds the six DOCX sources, exact renderer commits/trees, 45 export
assets per renderer, captured PDFs/HTML/reports, native output and labeled review
sheets. `Compose.py RUN BASELINE_SOURCE CANDIDATE_SOURCE` verifies those bindings
and retained pre-candidate contracts. `Mutations.py` rejects changed glyph widths,
heights, positions, missing/extra/duplicate/unpainted/reordered words and broken
page inventories. PyMuPDF 1.28.0 independently reads character advances and font flags:
separate IDs must each occupy 100pt; the mixed group must retain its four bold letters.
Mutants preserve total width while merging IDs or removing bold, and must still fail. `WidthChecks.py` reads no renderer code.

Related issue: [Docxodus #1564](https://github.com/JSv4/Docxodus/issues/1564).
The separate 65-character exact-fit request remains unresolved.

The first verifier incorrectly treated the aggregate extent of two independently
positioned regions as one glyph width. The retained `verifier-v1/` failure and
independent CSS control show Chromium rounds transformed text origins by about
0.25pt. The corrected check retains 0.1pt for **each region’s width** and uses the
existing 0.5pt position bound for their origins and aggregate extent. Single-region
width checks are unchanged. Offline HTML checks independently require every
carrier and painted region to have its authored width within 0.1pt.
