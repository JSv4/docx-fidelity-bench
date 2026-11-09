# Pending deleted rows in Markdown

Seven original reproducer/control pairs pin [Docxodus #1628](https://github.com/JSv4/Docxodus/issues/1628).
The default accepted projection must omit rows with `w:trPr/w:del`: middle rows, the first row,
a table's only row, a wrapped row, a merged row, and a row carrying a textbox. The seventh pair
forces opaque tables and checks dimensions. Controls retain the same rows without deletion marks.

The [baseline](baseline.json) passes 25/32 cases, failing all seven new reproducers; the
[candidate](candidate.json) passes 32/32, including all eighteen unchanged earlier diagnostics.
Exact text and saved-output schema are checked, with full source/build/fixture identities retained.
This is an unweighted projection diagnostic, not a Word rendering claim or PDF/redline score.
The separate engine tests cover public tracked deletion, patch removal, undo/reject restoration,
source-anchor retention, real empty rows and explicit inline-mode controls.

All inputs are original literal OOXML and Larch labels. No product fixtures or helpers are copied.
Screenshots show the recorded public Markdown, with anchor IDs shortened, in Chromium.

| Reproducer | Undeleted control |
| --- | --- |
| ![middle](deleted-row-middle.png) | ![middle control](deleted-row-middle-control.png) |
| ![first](deleted-row-first.png) | ![first control](deleted-row-first-control.png) |
| ![only](deleted-row-only.png) | ![only control](deleted-row-only-control.png) |
| ![wrapped](deleted-row-wrapped.png) | ![wrapped control](deleted-row-wrapped-control.png) |
| ![merged](deleted-row-merged.png) | ![merged control](deleted-row-merged-control.png) |
| ![textbox](deleted-row-textbox.png) | ![textbox control](deleted-row-textbox-control.png) |
| ![opaque](deleted-row-opaque.png) | ![opaque control](deleted-row-opaque-control.png) |

```bash
python3 -m bench.projection build --source /path/to/Docxodus --commit FULL_SHA --out runs/rows-build
python3 -m bench.projection run --build runs/rows-build --output runs/rows-result.json
python3 -m unittest discover -s tests -p test_projection.py -v
```
