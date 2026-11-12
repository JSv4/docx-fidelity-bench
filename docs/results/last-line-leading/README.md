# Last line leading

Two original Thistle documents hold 51 one-line paragraphs of 12 pt Liberation Serif with
`w:line="480"` (double) spacing. The text area is 23 full line pitches plus a remainder, set
through `w:pgMar/@w:bottom`: 15 pt in `last-line-leading-double-spare15` and 13 pt in
`last-line-leading-double-spare13`. Word puts a multiple's extra leading below the text and lets
the last line need only its text height, 2355/2048 x 12 = 13.7988 pt (Docxodus #1571).

| Case | Remainder | Lines on page 1 |
| --- | ---: | ---: |
| `last-line-leading-double-spare15` | 15 pt | 24 |
| `last-line-leading-double-spare13` | 13 pt | 23 |

`marker-region` assertions place `Thistle01` and the last fitting line on page 1, and the next
line on page 2.

**Native evidence.** Word 2024 opened copies of both inputs, with Liberation Serif renamed to
Times New Roman. `Range.Information` page numbers put 24 and 23 paragraphs on page 1. That matches
the issue author's `ExportAsFixedFormat` counts and the 0.05 pt bisection recorded in
[#1571](https://github.com/JSv4/Docxodus/issues/1571).

**Pending.** As for `text-placement`, no LibreOffice reference, score, retained PDF or
screenshot is included from this Windows host.
