# Logical-grid vertical merges

These five original inputs target Docxodus #1489. All packages validate with Open XML SDK 3.5.1 (Microsoft365). LibreOffice 25.8.7.3 renders each on one page with the complete expected token inventory and both declared column regions satisfied. These are independent LibreOffice diagnostic captures, not native Word references. The [production candidate run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41164103636) passes all five PDF and HTML mandatory checks. The [current-main run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41164106629) reproduces the failures. Independent review verified exact source, PDF and raster bindings; the aligned control’s delivered HTML and page PNG are byte-identical. Main cannot export the omitted continuation row, so that case has no baseline page image.

## tables-merge-grid-aligned-control

LibreOffice 25.8.7.3, full page at 96 DPI.

![tables-merge-grid-aligned-control — LibreOffice](tables-merge-grid-aligned-control-libreoffice.png)

Production candidate, full page at 96 DPI.

![tables-merge-grid-aligned-control — candidate](tables-merge-grid-aligned-control-candidate.png)

Production current main, full page at 96 DPI.

![tables-merge-grid-aligned-control — main](tables-merge-grid-aligned-control-baseline.png)

## tables-merge-grid-grid-before

LibreOffice 25.8.7.3, full page at 96 DPI.

![tables-merge-grid-grid-before — LibreOffice](tables-merge-grid-grid-before-libreoffice.png)

Production candidate, full page at 96 DPI.

![tables-merge-grid-grid-before — candidate](tables-merge-grid-grid-before-candidate.png)

## tables-merge-grid-multi-column

LibreOffice 25.8.7.3, full page at 96 DPI.

![tables-merge-grid-multi-column — LibreOffice](tables-merge-grid-multi-column-libreoffice.png)

Production candidate, full page at 96 DPI.

![tables-merge-grid-multi-column — candidate](tables-merge-grid-multi-column-candidate.png)

Production current main, full page at 96 DPI.

![tables-merge-grid-multi-column — main](tables-merge-grid-multi-column-baseline.png)

## tables-merge-grid-shifted

LibreOffice 25.8.7.3, full page at 96 DPI.

![tables-merge-grid-shifted — LibreOffice](tables-merge-grid-shifted-libreoffice.png)

Production candidate, full page at 96 DPI.

![tables-merge-grid-shifted — candidate](tables-merge-grid-shifted-candidate.png)

Production current main, full page at 96 DPI.

![tables-merge-grid-shifted — main](tables-merge-grid-shifted-baseline.png)

## tables-merge-grid-starter-grid-before

LibreOffice 25.8.7.3, full page at 96 DPI.

![tables-merge-grid-starter-grid-before — LibreOffice](tables-merge-grid-starter-grid-before-libreoffice.png)

Production candidate, full page at 96 DPI.

![tables-merge-grid-starter-grid-before — candidate](tables-merge-grid-starter-grid-before-candidate.png)

Production current main, full page at 96 DPI.

![tables-merge-grid-starter-grid-before — main](tables-merge-grid-starter-grid-before-baseline.png)
