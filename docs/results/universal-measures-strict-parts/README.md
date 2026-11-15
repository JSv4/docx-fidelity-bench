# Universal measures and a Strict chart part (Docxodus #1764)

`cases.png` shows each `core-v174` case. The columns are a desktop word processor's PDF (build 16.0.20326,
Windows 11, page 1 drawn with PyMuPDF), and Docxodus `main` at 644bbc9a and with the fix, each as its HTML render
in Chromium. These are illustrations, not registered references: the machine had no Liberation Serif, so
the word processor printed a substitute. The checked positions do not depend on the font.

| Case | Desktop word processor | Docxodus 644bbc9a | Docxodus with the fix |
| --- | --- | --- | --- |
| `section-page-universal-measures` | A4 (595.3 × 841.9pt), 56.7pt margins; `JuniperEdge` ends at 538.7pt | paginated page 612 × 792pt (Letter) | 595.3 × 841.9pt |
| `section-page-universal-measures-twips-control` | the same | 595.3 × 841.9pt | Unchanged |
| `chart-strict-part` | chart with values 41, 36, 29, its categories and a 0–50 axis | empty chart frame | chart with its bars, categories and axis |
| `chart-transitional-part-control` | the same | chart drawn | Unchanged |

The page cases write an A4 page with 2 cm margins as a Strict save writes every twips measure,
`w:pgSz w:w="595.30pt" w:h="841.90pt"` and `w:pgMar w:top="56.70pt"`, in a Transitional package
(Transitional's `ST_TwipsMeasure` admits the same universal measures). Docxodus parsed the page size as an
integer and fell back to Letter, so its page is 612 × 792pt and the right-aligned `JuniperEdge` ends at
555.3pt instead of 538.6pt. The control writes the same page in twips.

The chart cases put a bar chart with literal categories and values in a Transitional package. In
`chart-strict-part` the chart part alone is written in the Strict namespaces (the package shape of
Docxodus #1702), with its colour transform as `a:lumMod val="75%"`. Docxodus converted Strict content only
when the main document was Strict, so its chart renderer found no Transitional `c:chart` and drew an empty
frame, missing every chart token. The value axis is pinned to 0–50 in steps of 10 so every renderer prints
the same six labels.
