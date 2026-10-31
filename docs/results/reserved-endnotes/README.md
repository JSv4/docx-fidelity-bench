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

Docxodus baseline/candidate PDF comparisons are pending. Native converter regressions
reproduce the notice leak on main and pass with the shared typed-note filter. Full-suite
rendering and Word scoring are not claimed.
