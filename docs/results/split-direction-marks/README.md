# Direction marks in moved text (Docxodus #1862)

Docxodus's HTML converter writes invisible direction marks: U+200E after a line break in a left-to-right
paragraph, and U+200F at the start of a right-to-left paragraph and around each right-to-left run. Two steps
of the converter move text it has already rendered to a new parent: the paginated view splits a paragraph
at a page or column break into one piece per page or column, and a link inside a HYPERLINK field's result is
unwrapped into the field's own link. Docxodus `main` at `9af576ec` moved that text by copying it, and the copy
of a mark is the plain text `#x200e` or `#x200f`, so the paginated view and PDF export printed those words.

The PDF track's visible-word inventory leaves out the marks themselves (see `docs/SCORING.md`) but counts the
printed text, so each reproducer fails its inventory on `main` and passes with the fix.

| Case | What it holds | Its control |
| --- | --- | --- |
| `direction-mark-page-split-ltr` | `TamariskLanding`, a line break, `TamariskBeacon`, a page break, `TamariskCove` | `-control`: no page break |
| `direction-mark-page-split-rtl` | a `w:bidi` paragraph: right-to-left runs `TamariskQuay`, a page break, `TamariskMole` | `-control`: a line break in the page break's place |
| `direction-mark-field-link-line-break` | a `w:hyperlink` holding `TamariskChart`, a line break and `TamariskSounding`, inside a complex HYPERLINK field's result | `-control`: the same link outside any field |

Each control's package differs from its reproducer only in `word/document.xml`, by the page-break run or the
field's characters (`tests/test_direction_marks.py`). The right-to-left control keeps a line break where the page
break was, so each label still has a line of its own: the order of two right-to-left runs sharing a line is a
separate question the reproducer never asks. Every case pins each label to its page with a whole-page
`marker-region` check, so a page break that a renderer dropped, or a label it printed glued to `#x200e`, fails too.
The line break that writes the left-to-right mark is pinned as well: a `marker-reference-position` check requires
`TamariskBeacon` and `TamariskSounding`, the words after it, to start where the LibreOffice reference starts them,
within 0.5pt. A renderer that lost the break while moving the text, and printed both words on one line, would
otherwise pass every check.

## Measurements

| Case | Kind | LibreOffice 25.8.7.3 | Docxodus main `9af576ec` | Docxodus fix `d368acdc` |
| --- | --- | --- | --- | --- |
| `direction-mark-page-split-ltr` | reproducer | pass; calibration 100.00 | **fail** (`#x200eTamariskBeacon`; `TamariskBeacon` not found for its position); raster 85.46 | pass; raster 99.85, close |
| `direction-mark-page-split-ltr-control` | control | pass; calibration 100.00 | pass; raster 99.73, close | pass; raster 99.73, close |
| `direction-mark-page-split-rtl` | reproducer | pass; calibration 100.00 | **fail** (`x200f`, `#x200fTamariskQuay`, `#x200f`, `#`, `x200fTamariskMole#x200f#`); raster 50.11 | pass; raster 99.99, close |
| `direction-mark-page-split-rtl-control` | control | pass; calibration 100.00 | pass; raster 99.87, close | pass; raster 99.87, close |
| `direction-mark-field-link-line-break` | reproducer | pass; calibration 100.00 | **fail** (`#x200eTamariskSounding`; `TamariskSounding` not found for its position); raster 76.73 | pass; raster 91.05, **not close** |
| `direction-mark-field-link-line-break-control` | control | pass; calibration 100.00 | pass; raster 99.84, close | pass; raster 99.84, close |

"Pass" and "fail" are the **mandatory PDF checks only**: the complete visible-word inventory, the declared font
family, the page of each label and the position of the word after each line break. `Compose.py` applies them with
`bench.pdf.correctness` against the LibreOffice reference, as `bench run` does. Each failure on `main` is
`expected-visible-tokens` plus the `marker-region` check of each label printed glued to a mark, and, in the
left-to-right and field-link reproducers, the `marker-reference-position` check of that same label; the words in
parentheses are the ones the inventory did not expect. A mandatory failure makes the case score zero, so the three
reproducers score 0 on `main`; their raster figure is shown only to describe the page. With the fix, and in every
control on both builds, `TamariskBeacon` and `TamariskSounding` start 0.10pt left of and 0.003pt below the
reference's position.

The fix passes by keeping the marks as characters, not by dropping them. `evidence.json` records, for each delivered
PDF and HTML file, the raw PDF words that still hold U+200E or U+200F and how often the HTML's visible text holds the
mark characters and the printed names:

| Case | `main` HTML text | fix HTML text | PDF raw words holding a mark, both builds where printed |
| --- | --- | --- | --- |
| `direction-mark-page-split-ltr` | `#x200e` ×1 | U+200E ×1 | none |
| `direction-mark-page-split-rtl` | `#x200f` ×5 | U+200F ×5 | fix: `\u200f`, `\u200fTamariskMole` |
| `direction-mark-field-link-line-break` | `#x200e` ×1 | U+200E ×1 | none |
| each control | U+200E ×1 (U+200F ×6 right to left) | the same | right to left: `\u200f`, `\u200fTamariskMole` |

Neither build prints a mark's name in any control, and the fix never does. Poppler keeps U+200F in the raw words of
the right-to-left pages and reports none for the left-to-right mark after a line break.

"Raster" is the worst page's `100 × min(SSIM, ink F1)` against the LibreOffice reference, computed with
`bench.metrics.page_metrics` on Poppler's 96-DPI CropBox rasters exactly as `bench run` computes it; "close" is
SSIM ≥ 0.98 and ink F1 ≥ 0.95 on every page with every mandatory check passing. The field-link reproducer's worst
page has SSIM 0.9979 and ink F1 0.9105 with the fix: Docxodus renders the HYPERLINK field as a bare link that takes
the browser's default underline, which LibreOffice does not draw (on `main` the text is also blue, because the
copied runs lost their formatting). That raster stays below close until
[Docxodus #1869](https://github.com/JSv4/Docxodus/issues/1869) is fixed, while the case's mandatory checks isolate
#1862. Every other fix result and every control is close on both builds. `evidence.json` holds each page's SSIM,
ink F1, precision and recall.

All six LibreOffice references are eligible, and the LibreOffice identical-engine calibration scores 100 on each
with the `close` gate. The two Docxodus columns are **unscored diagnostics**, not registered candidate scores: the
benchmark's own adapter reports `ENVIRONMENT_INELIGIBLE` on this host, which denies the user namespaces its pinned
Chromium sandbox needs, so the PDFs were captured with `docs/results/export-reliability/Capture.mjs` through the
public export API in a system Chrome 158.0.8127.36 with its sandbox on, strict fonts and the hashed Liberation Serif
directory, with the delivered HTML (`--html`).

Both renderers were built with `bench build-docxodus` from clean detached worktrees: `main` at
`9af576ecded6cd820647b38e79864665e8d1568f` and the fix at `d368acdc112216301271e293ddf4359a11fe7a4f`, the head
with which [JSv4/Docxodus#1866](https://github.com/JSv4/Docxodus/pull/1866) merged (as `2d8ca447`). Both are on
Docxodus `main`. An earlier version of this page measured `5bdf3f8b`, a local commit of that pull request that was
never published. `d368acdc` changes no line of `Docxodus/WmlToHtmlConverter.cs` against it (its other changes are
the #1861 session commits it sits on), and every page raster and extracted word above is identical to that earlier
measurement.

`evidence.json` binds the six-case diagnostic manifest `diagnostic-e7cd6d679764`, selected with
`bench.suites.select_cases` from `core-v178` as `bench/fixtures.py` generates it (generator SHA-256
`16d6f2d167d950b95085a3fe77be54ff52e98022fc94f9da05b69a35ce858dac`). `reference-bundle.json` is the LibreOffice bundle
registered for that manifest.

## Shapes

- The line break comes before the page break: LibreOffice 25.8.7.3 drops a page break that a line break directly
  follows, and prints both labels on one page.
- The right-to-left runs hold Latin labels. Poppler extracts Hebrew words from the LibreOffice PDF in visual order
  (reversed), so a Hebrew inventory could not be met by the reference. Docxodus writes the marks around a run
  marked `w:rtl` whatever its script. The runs state `w:szCs` so that every renderer prints them at 11pt.

## Pending

Word reference registration and full-suite scoring for `core-v178` remain pending; no Word capture was made for
these cases. The suite was first numbered `core-v176`; renumbering changed no input.

## Reproduce

`evidence.json` binds the manifest, the reference bundle and its environment, the calibration result, both build
identities, the capture and inspection records, every check result and page measurement, where each build's marks
went, and the hashes of every PDF, delivered HTML file, page raster and screenshot. `reference-bundle.json` is the LibreOffice bundle. With `MANIFEST` holding only these six cases,
`ENVIRONMENT` the JSON that `bench.environment.environment(['Liberation Serif'])` returns, and `RUN` a scratch
directory:

```sh
python3 -m bench build-docxodus --source SOURCE --commit FULL_SHA   # for each build
python3 -m bench reference libreoffice --manifest MANIFEST --out RUN/reference
python3 -m bench run --manifest MANIFEST --reference RUN/reference/bundle.json --adapter libreoffice \
  --candidate reference-calibration --out RUN/calibration --gate close
node docs/results/export-reliability/Capture.mjs SOURCE MANIFEST RUN/capture-main ENVIRONMENT --html
python3 docs/results/export-reliability/Inspect.py MANIFEST RUN/capture-main/capture.json
python3 docs/results/split-direction-marks/Compose.py RUN
```

Repeat the capture and inspection for `RUN/capture-fix`, and copy each source's `.docx-bench-build.json` to
`RUN/main-docx-bench-build.json` and `RUN/fix-docx-bench-build.json` before composing. `Compose.py` measures the
rasters and draws the sheets from the same unchanged pixels, every page of a case cropped to the box around all
three renderers' ink.

![LTR page split](direction-mark-page-split-ltr.png)

![LTR control](direction-mark-page-split-ltr-control.png)

![RTL page split](direction-mark-page-split-rtl.png)

![RTL control](direction-mark-page-split-rtl-control.png)

![Field link](direction-mark-field-link-line-break.png)

![Field link control](direction-mark-field-link-line-break-control.png)
