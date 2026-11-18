# Formatting restored to its own run (Docxodus #1784)

Docxodus #1784 found a comparison that, for a paragraph whose text is unchanged but whose formatting changed,
archived each run's original formatting on the wrong run. It located a run's original formatting with a cursor
that counted only `w:t` text, while a symbol counts as one character, a tab or break run has no text, and a run
inside a hyperlink was skipped. Neither round trip reads character formatting, so `run-formatting` declares the
formatted spans of each resolved endpoint.

| Case | Kind | Failed checks, baseline | Rejected spans, baseline | Failed checks, candidate |
| --- | --- | --- | --- | --- |
| `redline-format-only-symbol` | reproducer | `assertion-run-formatting`, `assertion-revision-count` | `Lead \uf0b7bold` plain, ` plain tail` bold | none |
| `redline-format-only-tab` | reproducer | `assertion-run-formatting` | the tab bold instead of underlined | none |
| `redline-format-only-hyperlink` | reproducer | `assertion-run-formatting` | `linked` plain, ` plain tail` bold | none |
| `redline-format-only-plain-control` | control | none | as the original | none |

Baseline is Docxodus main `6c98b822`; candidate is the fix commit `1ec8ec7b`
([JSv4/Docxodus#1784](https://github.com/JSv4/Docxodus/issues/1784)). The authored redlines pass every check, and
LibreOffice's comparisons apply to all four cases. "Failed checks" are the bench's own markup comparisons, SDK
validation, assertions and the LibreOffice text round trips, run on Linux with LibreOffice 25.8.7.3. No reference
application capture was made for these cases. `evidence.json` holds each run's failed checks and the observed
rejected spans.
