# Fractional whole-number measures

Eight original Quillwort inputs accompany [Docxodus #1622](https://github.com/JSv4/Docxodus/issues/1622).
Each input writes a bare decimal in a whole-number measure: border `w:sz="4.5"` in paragraph, table
and cell borders, or `w:gridCol w:w="4000.5"`. Each has a control holding the whole value that
Word 2024 reads, `w:sz="4"` or `w:w="4000"`. Within a pair only that one attribute value differs.

Word 2024 opens independently authored equivalents of these inputs and truncates toward zero
(4.5 → 4, 4.6 → 4, 5.5 → 5, 8.9 → 8; 4000.5 → 4000, 4001.5 → 4001). This was read back through
`Document.WordOpenXML` and the object model. Docxodus 15.1.0 fails the conversion of every input,
while the controls convert. The checks cover marker positions and the declared rule widths: 0.5pt
for the border cases and 1pt for the grid case.

LibreOffice reference captures and candidate scoring are pending. This machine has no pinned
LibreOffice, so no reference bundle is included and no eligibility or fidelity score is claimed.
All 1,066 prior input hashes are unchanged.
