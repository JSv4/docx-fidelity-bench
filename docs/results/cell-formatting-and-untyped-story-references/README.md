# Formatting inside table cells and untyped story references (Docxodus #1797, #1803)

Docxodus #1797 found a comparison whose table, row and cell checks compared only the cells' text, so a cell
changed only in formatting was copied from the revision untracked and reject kept the new formatting.
Docxodus #1803 found a redline that kept a header or footer reference written without `w:type` and added a
typed default one beside it, so the section had two default references. Neither round trip reads character
formatting, paragraph marks or section references, so the cases declare `run-formatting`, `mark-formatting`
and `section-stories`; every case bounds `revision-count` to its own records.

| Case | Kind | Baseline `fbabfaf4` | #1797 fix `c4d7be13` | #1803 fix `701bbec8` | Both fixes `4cad9bee` |
| --- | --- | --- | --- | --- | --- |
| `redline-cell-bold` | reproducer | `assertion-run-formatting` | none | `assertion-run-formatting` | none |
| `redline-cell-mark-size` | reproducer | `assertion-mark-formatting` | none | `assertion-mark-formatting` | none |
| `redline-cell-bold-beside-edit` | reproducer | `assertion-run-formatting` | none | `assertion-run-formatting` | none |
| `redline-cell-bold-edit-control` | control | none | none | none | none |
| `redline-untyped-header-changed` | reproducer | `assertion-section-stories` | `assertion-section-stories` | none | none |
| `redline-untyped-footer-changed` | reproducer | `assertion-section-stories` | `assertion-section-stories` | none | none |
| `redline-typed-header-changed-control` | control | none | none | none | none |

Each cell lists the failed checks. The fix commits are the heads of the Docxodus pull requests for
[#1797](https://github.com/JSv4/Docxodus/issues/1797) and [#1803](https://github.com/JSv4/Docxodus/issues/1803).
`4cad9bee` is a merge of the two, made only for scoring (its tree, `7d961305`, is what `git merge-tree` gives for
the two heads); each fix passes its own reproducers and both controls, and the merge passes all seven. The authored
redlines pass every check. Checks are the bench's markup comparisons, SDK validation, assertions and the LibreOffice
text round trips, run on Linux with LibreOffice 25.8.7.3. No reference application capture was made for these
cases. `evidence.json` holds each run's failed checks, revision counts, rejected spans or marks, and section stories.
