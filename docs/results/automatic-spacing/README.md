# Automatic and contextual paragraph spacing

Eight original Marram inputs accompany [Docxodus #1553](https://github.com/JSv4/Docxodus/issues/1553).
All text is 12pt Liberation Serif on exact 16pt lines. Three inputs set `w:beforeAutospacing` and
`w:afterAutospacing` with explicit `w:before="100" w:after="100"`: at the first paragraph of the
document, in a table cell, and next to a table. Each control drops only the two flags. The fourth
pair puts `w:contextualSpacing` on the first or the second of two same-style paragraphs, with 5pt
after on the first and 14pt before on the second.

The marker regions are Word 2024's PDF word boxes for these exact inputs, with the fonts renamed to
their metric twins (Times New Roman), and a 1pt tolerance. Word gives no automatic space before the
first paragraph of the document or at the top and bottom of a cell, 14pt between paragraphs in a cell
and next to a table, and ignores the explicit values. With contextual spacing on the first paragraph,
the 5pt it gives up still absorbs 5pt of the next paragraph's 14pt, leaving 9pt; on the second, the
first paragraph's 5pt remains.

LibreOffice reference captures and candidate scoring are pending. This machine has no pinned
LibreOffice, so no reference bundle is included and no eligibility or fidelity score is claimed.
All prior input hashes are unchanged.
