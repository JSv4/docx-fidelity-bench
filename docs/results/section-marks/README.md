# Empty section marks

Eight original Heron and Kestrel inputs accompany [Docxodus #1572](https://github.com/JSv4/Docxodus/issues/1572).
Each input holds an empty paragraph whose only content is a `w:sectPr`. Three put it between two
lines, before a continuous section: single-spaced, with 8 pt after and 1.08 line spacing, and before
a two-column section. The fourth puts one after each of two page breaks, before next-page sections.
Each control carries the same break on the preceding line, or drops the page breaks, which in
Word 2024 gives the same layout.

Word 2024 printed independently authored equivalents (Times New Roman). It sets the empty mark at
the end of the preceding paragraph's last line, so the next line steps 13.80 pt (22.92 pt when
spaced), as with no mark, and the page-break document has three pages, not five. The mark's own
spacing, run size and the next section's columns make no difference. Docxodus before the fix stepped
27.59 pt (45.78 pt spaced) and rendered five pages.

Word 2024 also printed these eight inputs, substituting its own font for Liberation Serif. Each
case matches its control: 12.60 pt between the Heron lines (21.60 pt spaced, 12.60 pt before two
columns) and three pages for both Kestrel documents. Docxodus with the fix steps 12.69 pt and
21.69 pt (its empty mark is a one-twip box) and renders three pages. Each PNG here shows one case,
Word 2024 above Docxodus with the fix, labeled with each renderer's page count.

The checks compare marker positions with the reference, and put each Kestrel section's two lines on
its own page (1, 2 and 3). LibreOffice reference captures and candidate scoring are pending. This
machine has no pinned LibreOffice, so no reference bundle is included and no eligibility or fidelity
score is claimed. All 1,066 prior input hashes are unchanged.
