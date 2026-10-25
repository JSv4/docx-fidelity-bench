# Separate Word reference evidence

This supports [Docxodus #1124](https://github.com/JSv4/Docxodus/issues/1124) and [PR #1376](https://github.com/JSv4/Docxodus/pull/1376). Word and LibreOffice are separate reference providers. There is currently one renderer layout mode, recorded as `default`. This harness change adds no public layout option and changes no scorer, tolerance, authored fixture, or historical LibreOffice reference.

Eight exact Word captures pass local reference registration. The immutable source/PDF capture pack has SHA-256 `90846f6970f5779d99e2b29234a7682f61dac6630eb53620c38498e2100ca1fc` (3,925,542 bytes). It contains original authored document parts, separately licensed unmodified Liberation Serif source fonts with their OFL notice, raw native PDFs, and font identity audits. It is kept outside the source inventory. Word emits internal font aliases; only the reviewed source/program hash bindings qualify these exact captures. The harness verifies those bindings and does not independently repeat the operator's outline audit. No font hinting or raster identity is claimed.

The table below is a **raw 96 DPI diagnostic using unchanged metric v3**, not a strict benchmark score. Main is `9b03f6c45e6974ffa2111df4567637f79a62423b` (merged as `0ef03ea3a4f8697633f17adc9fa42686c60b45b4`); candidate is `7954e593614574a094bd0c0104c332d24377f444`. The renderer source and built artifact hashes were guarded. The agreement candidate was exported before its commit; unchanged production source/artifacts were subsequently bound to that commit. All five compared metrics hold or improve on every page of these eight Word comparisons. Separate strict CI measurement is still required.

| Original case | Main against Word | Candidate against Word |
| --- | ---: | ---: |
| paragraph-contract | 84.13657 | 95.68475 |
| columns-continuous | 88.69283 | 95.41453 |
| columns-balanced | 88.82131 | 95.03262 |
| columns-break | 89.46166 | 95.10126 |
| paragraph-keep | 87.58558 | 96.33701 |
| paragraph-heading | 99.62340 | 99.62892 |
| images-square | 92.85629 | 96.69403 |
| images-tight | 93.17152 | 96.72707 |

For all eight cases, the candidate output from the embedded-font/schema-order capture input has exactly the same unretouched 96 DPI PPM bytes as the original immutable CI input. This supports applying the Word evidence to those original cases. Input semantics are independently checked through equal document/style property trees. This evidence does not establish interchangeable input packages for arbitrary future renderer changes: CI must repeat that raster equivalence check. The original LibreOffice result and all its declines remain separate, visible evidence.

[Machine-readable evidence](evidence.json) records input, PDF and PNG hashes. [Original CI raster equivalence](original-ci-raster-equivalence.json) records every protected page hash. All 33 provider pages in these 11 panels were visually inspected; the nine earlier panels are copied byte for byte from their prior review. Each panel is a full physical page at the same scale, with labels outside the page: Word on the left, main in the middle, candidate on the right.

## paragraph-contract

![paragraph-contract: Word, main, candidate](paragraph-contract-page-1.png)

![paragraph-contract: Word, main, candidate](paragraph-contract-page-2.png)

## columns-continuous

![columns-continuous: Word, main, candidate](columns-continuous-page-1.png)

## columns-balanced

![columns-balanced: Word, main, candidate](columns-balanced-page-1.png)

## columns-break

![columns-break: Word, main, candidate](columns-break-page-1.png)

## paragraph-keep

![paragraph-keep: Word, main, candidate](paragraph-keep-page-1.png)

![paragraph-keep: Word, main, candidate](paragraph-keep-page-2.png)

## paragraph-heading

![paragraph-heading: Word, main, candidate](paragraph-heading-page-1.png)

![paragraph-heading: Word, main, candidate](paragraph-heading-page-2.png)

## images-square

![images-square: Word, main, candidate](images-square-page-1.png)

## images-tight

![images-tight: Word, main, candidate](images-tight-page-1.png)
