# Reserved endnotes (#1485)

Four original inputs exercise positive-id note classification. Each LibreOffice 25.8.7.3
PDF has one page and exactly the manifest's token inventory. This is diagnostic output,
not a fresh Word reference. The ordinary control includes its citation and note markers.

| Input | LibreOffice page |
|---|---|
| Uncited continuation notice | ![LibreOffice: continuation notice](notes-reserved-continuationnotice-libreoffice.png) |
| Uncited continuation separator | ![LibreOffice: continuation separator](notes-reserved-continuationseparator-libreoffice.png) |
| Uncited separator | ![LibreOffice: separator](notes-reserved-separator-libreoffice.png) |
| Cited ordinary note | ![LibreOffice: ordinary note](notes-reserved-normal-libreoffice.png) |

Production PDF evidence:

- [Baseline main 1240cc5](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41160144240)
- [Candidate 9809b579](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41160142623)

All four cases were measured in both runs. The baseline leaks the continuation notice and
fails its exact visible-token check; the other three controls pass. The candidate passes
all mandatory checks (page count, exact tokens, declared fonts and geometry) on all four.
The notice fidelity score rises from 0 to 99.997; controls are unchanged (99.997 for each
separator, 96.142 for the cited ordinary note). This targeted set is not a full-suite score.

| Case | Docxodus baseline | Docxodus candidate |
|---|---|---|
| continuationnotice | ![Docxodus baseline: continuationnotice](notes-reserved-continuationnotice-docxodus-baseline.png) | ![Docxodus candidate: continuationnotice](notes-reserved-continuationnotice-docxodus-candidate.png) |
| continuationseparator | ![Docxodus baseline: continuationseparator](notes-reserved-continuationseparator-docxodus-baseline.png) | ![Docxodus candidate: continuationseparator](notes-reserved-continuationseparator-docxodus-candidate.png) |
| separator | ![Docxodus baseline: separator](notes-reserved-separator-docxodus-baseline.png) | ![Docxodus candidate: separator](notes-reserved-separator-docxodus-candidate.png) |
| normal | ![Docxodus baseline: normal](notes-reserved-normal-docxodus-baseline.png) | ![Docxodus candidate: normal](notes-reserved-normal-docxodus-candidate.png) |
