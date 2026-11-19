# Paragraph marks and indented copies (Docxodus #1794, #1793)

Docxodus #1794 found a comparison that paired paragraphs without their marks, so a change to a paragraph mark's own
run properties was left untracked and reject kept the revised mark. Docxodus #1793 found its IR hash keeping
indentation between elements, so an indented copy read as edited. Neither round trip reads paragraph marks, so
`mark-formatting` declares each mark's size; every case bounds `revision-count` to its own records.

| Case | Kind | Baseline `9704704e` | #1794 fix `24a31a1e` | #1793 fix `685b3e10` | Both fixes `00708712` |
| --- | --- | --- | --- | --- | --- |
| `redline-mark-size-blank` | reproducer | `assertion-mark-formatting` | none | `assertion-mark-formatting` | none |
| `redline-mark-size-leading-blanks` | reproducer | `assertion-mark-formatting` | none | `assertion-mark-formatting` | none |
| `redline-mark-size-text` | reproducer | `assertion-mark-formatting` | none | `assertion-mark-formatting` | none |
| `redline-mark-size-centred-control` | control | none | none | none | none |
| `redline-indented-copy` | reproducer | `assertion-revision-count`, `assertion-untracked-text`, `markup-accepted`, `markup-rejected` | `assertion-revision-count`, `assertion-untracked-text`, `markup-accepted`, `markup-rejected` | none | none |
| `redline-indented-copy-control` | control | none | none | none | none |

Each cell lists the failed checks. Each fix passes its own reproducers and both controls; `00708712`, the head of
[JSv4/Docxodus#1799](https://github.com/JSv4/Docxodus/pull/1799) after merging `main` with
[#1798](https://github.com/JSv4/Docxodus/pull/1798), passes all six. The authored redlines pass every check. Checks are
the bench's markup comparisons, SDK validation, assertions and the LibreOffice text round trips, run on Linux with
LibreOffice 25.8.7.3. No reference application capture was made for these cases. `evidence.json` holds each run's
failed checks, revision counts and rejected marks.
