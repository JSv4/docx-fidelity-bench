# Adjacent table property captures

These four original cases declare a 4,800-twip first table with zero left cell margin and a
6,000-twip second table with a colored border and 720-twip left margin. Final and original review
profiles each have a control with an empty paragraph between the tables.

The sheets show the LibreOffice reference and actual Docxodus PDFs before and after the fix.
All four sheets were visually inspected. Candidate PDFs use a caller-owned diagnostic Chromium
browser because the local host cannot establish Chromium's process sandbox. They have
`browserObserved` verification and are **unmeasured for production scoring**. Neither the host
check nor the benchmark adapter was bypassed; its recorded candidate attempt is ineligible.
The implementation's committed export tests retain sandboxing for CI.

LibreOffice 25.8.7.3 imports the adjacent pair as one two-row table, using the second table's
6,000-twip width and 720-twip margin. A separate load/save round trip confirms this structure.
It leaves the paragraph-separated control as two one-row tables, with widths 4,800 and 6,000
and margins 0 and 720. Consequently the LibreOffice raster for the plain pair differs from the
source-boundary-preserving behavior documented for Word in Docxodus #1341. The local after
capture retains each source table; the before capture uses the first table's properties and
loses the second border/margin. The controls retain the second border in both versions.

All four reference-provider calibration cases score 100. This proves capture consistency,
not the intended table-boundary semantics. The focused bundle contains four of 275 required
PDF cases and makes no full-suite claim. Complete token inventories, raw PDFs, reference
eligibility and unaligned raster measurements remain unchanged. No new Word capture is claimed.

`capture.json` records exact source commits and build identities, input/PDF/raster/sheet hashes,
SDK validation, the LibreOffice round-trip observations and the focused calibration contract.
