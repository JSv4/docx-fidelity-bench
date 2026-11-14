# Grid columns no row reaches (Docxodus #1750)

`cases.png` shows the top of page 1 of each `core-v173` case. The columns are Word 2024 (16.0.20326,
Windows 11, `ExportAsFixedFormat` to PDF), Docxodus `main` at 0af51ef5, and Docxodus with the fix. Each
page is drawn from its PDF with pdf.js. These are illustrations, not registered references: the machine
had no Liberation Serif, so Word and Docxodus both printed a substitute. The checked positions do not
depend on the font.

| Case | Word 2024 | Docxodus 0af51ef5 | Docxodus with the fix |
| --- | --- | --- | --- |
| `table-grid-unused-columns-trailing` | `QuinceUnit1` at 162.5pt, `QuinceSum1` at 387.6pt | 122.5pt and 247.5pt | 162.5pt and 387.5pt |
| `table-grid-unused-columns-filled-control` | `QuinceUnit1` at 122.5pt, `QuinceSum1` at 247.6pt | 122.5pt and 247.5pt | Unchanged |

The table is a fixed 450pt grid of 50, 125, 75, 100 and 100pt columns at the 72pt margin, with no cell
margins. In the reproducer every row has three cells and `w:gridAfter w:val="2"`. Word drops the two
columns no row reaches and widens the other three in proportion until the table spans its 450pt
preferred width (90, 225 and 135pt). Docxodus kept the grid's widths and left the unused columns empty.
In the control the last row fills all five columns, so every column stays and nothing widens.
