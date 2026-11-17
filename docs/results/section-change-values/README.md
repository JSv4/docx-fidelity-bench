# Values a section change leaves out

Docxodus #1775 reports three ways a comparison's section property change misleads a desktop word processor (build
16.0.20326), though Docxodus's own revision engine accepts and rejects each one correctly. Docxodus wrote each
side of a `w:sectPrChange` as the document it came from wrote it, so a value one side left at its default was not
stated there. That application is reported to read a missing value as unchanged rather than as its default: it
rejected a portrait-to-landscape change whose archive had no `w:orient` to landscape, and saw no change in a final
section that dropped `w:titlePg` beside an archive that kept it. A paragraph whose only change was its section break
also gave its run an empty `w:rPrChange`, a formatting revision on text nobody reformatted.

| Case | Kind | Failed checks, baseline | Observed, baseline | Failed checks, candidate | Observed, candidate |
| --- | --- | --- | --- | --- | --- |
| `redline-section-orientation-default` | reproducer | `assertion-section-change-values` | orientation landscape, archived none | none | landscape, archived portrait |
| `redline-inline-section-orientation-default` | reproducer | `assertion-section-change-values`, `assertion-revision-count` | landscape, archived none; 2 revision records | none | landscape, archived portrait; 1 |
| `redline-section-orientation-stated-control` | control | none | landscape, archived portrait | none | landscape, archived portrait |
| `redline-section-title-page-off` | reproducer | `assertion-section-change-values` | title page none, archived on | none | off, archived on |
| `redline-section-title-page-off-stated-control` | control | none | off, archived on | none | off, archived on |
| `redline-section-page-width-runs` | reproducer | `assertion-revision-count` | 2 revision records | none | 1 |
| `redline-section-page-width-runs-bold-control` | control | none | 2 | none | 2 |

Baseline is Docxodus main `d99765d7`; candidate is the PR head `e8650941` (the fix, with main's dependency bumps merged in). The authored redlines pass every check, with the
same observed values as the candidate. "Failed checks" are the bench's own markup comparisons, SDK validation and
assertions, run on Linux with LibreOffice 25.8.7.3. LibreOffice shows no revision for a change to section properties
alone, so its comparisons are declared ineligible for every case but the bold control, where both pass. Across the
whole `redline-v53` suite (run at the fix commit `e5a9f683`, before that merge, with the two #1771 inline
title-page cases still declared LibreOffice-eligible), 338 of 343 cases were measured for each: the candidate
changes no other case's score, the four reproducers go from 0 to 100, and every case that fails or is unmeasured
with the candidate does so with the baseline too. Those two #1771 cases were unmeasured in both runs because
LibreOffice shows no revision for their section-only change; they are now declared ineligible and pass for both.

No desktop word processor was available where these cases were made, so this page holds no reference capture: the
reference application's behaviour is as the issue reports it, not re-measured here. `evidence.json` holds each run's
failed checks and the observed redline values.
