# Notes at a page foot

Four original Rowan cases accompany [Docxodus #1738](https://github.com/JSv4/Docxodus/issues/1738).
Each paragraph is 10pt Liberation Serif, justified and double-spaced (`w:line="480"`), and cites a
one-line footnote about 70% of the way through, after a `RowanCite` label. Each note opens with its
`RowanNote` label. The document defaults state `w:line="278"`, so a note line is 1.158 lines.
`RowanEnd` closes the last paragraph.

| Case | Input | Word 2024 | Docxodus `main` at `a8b1d6ce` |
|---|---|---|---|
| `notes-page-foot-citing-line` | five paragraphs; the fifth would end page 1 | page 1: 23 lines, notes 1–4; page 2: the fifth paragraph's citing line and last line, note 5 | export fails: "A footnote continuation is clipped in the final page tree" |
| `notes-page-foot-citing-line-control` | the first four paragraphs alone | one page, notes 1–4 | as Word |
| `notes-page-foot-uncited-line` | the first paragraph cites two notes, the fifth none; compatibility mode 14 | one page: 25 lines, notes 1–5 | export fails, as above |
| `notes-page-foot-one-and-a-half-control` | eight paragraphs at `w:line="360"` | page 1: notes 1–6; page 2: notes 7–8 | as Word |

`marker-region` assertions put each `RowanNote` label and `RowanEnd` on the page Word prints them
on; `same-page` assertions keep each `RowanCite` label with its note.

Word 2024 (build 16.0.20326) printed these exact inputs with the font renamed to Times New Roman
(`SaveAs2` to PDF), and every marker landed on the page its region names. Under widow control Word
keeps a paragraph's leading beside the notes it brings, so the fifth paragraph breaks before its
citing line and that line moves to page 2 with its note. Before compatibility mode 15, a paragraph
that brings no note may end the page with its leading under the note band. In mode 15, which the
other three inputs use, Word keeps that leading above the band: the same uncited input in mode 15
prints 23 lines and moves the last two to page 2. These cases do not pin that mode 15 behaviour,
which Docxodus does not yet model. The `main` column is from these inputs printed through its PDF
export. A build of the Docxodus change for #1738 puts every marker on its page, by the word boxes
read with PyMuPDF; the bench's own inspection was not run here.

| Case | Docxodus with the #1738 change |
|---|---|
| `notes-page-foot-citing-line` | ![citing line](notes-page-foot-citing-line.png) |
| `notes-page-foot-citing-line-control` | ![four paragraphs](notes-page-foot-citing-line-control.png) |
| `notes-page-foot-uncited-line` | ![uncited line](notes-page-foot-uncited-line.png) |
| `notes-page-foot-one-and-a-half-control` | ![1.5 lines](notes-page-foot-one-and-a-half-control.png) |

LibreOffice reference captures and candidate scoring are pending. This machine has no pinned
LibreOffice, so no reference bundle is included and no eligibility or fidelity score is claimed.
All prior input hashes are unchanged.
