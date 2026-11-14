# Content placed wholly past the paper edge (Docxodus #1733, #1734)

`cases.png` shows page 1 of each `core-v170` off-paper case and its control. The columns are Word 2024
(16.0.20326, Windows 11, `SaveAs2` to PDF), Docxodus `main` at a8b1d6ce, and Docxodus with the fix.
Each page is drawn from its PDF with pdf.js. These are illustrations, not registered references: the
machine had no Liberation Serif, so Word and Docxodus both printed Times New Roman in its place.

| Case | Word 2024 | Docxodus a8b1d6ce | Docxodus with the fix |
| --- | --- | --- | --- |
| `offpaper-table-cell-beyond` | One page; `PawpawChecked` at 493pt, `PawpawSigned` absent | Refused: `has no measurable fragment` | One page; `PawpawChecked` at 492pt, `PawpawSigned` absent |
| `offpaper-table-cell-edge-control` | One page; `PawpawChecked` at 493pt | Exports | Unchanged |
| `offpaper-linked-story-below` | One page; no frame and no story text | Refused: `has no measurable fragment` | One page; no frame and no story text |
| `offpaper-linked-story-on-paper-control` | One page; both story words in the first frame | Exports | Unchanged |

Word places the crossing cell and the linked frames where the source puts them and clips at the paper edge.
A first version of the table control dropped the off-paper cell and left the last grid column unused in every
row. Word then widened the remaining columns to fill the table width, so the crossing cell moved to 603pt and
its word was cut at the edge. The control instead spans the crossing cell over the last column.
