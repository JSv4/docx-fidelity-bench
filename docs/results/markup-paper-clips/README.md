# Source-paper clipping beside balloons

Seven original Elm documents isolate the source-textbox failures in
[Docxodus #1558](https://github.com/JSv4/Docxodus/issues/1558). They use 11pt Liberation
Serif, 16pt exact spacing, Letter paper and a 150 × 80pt DrawingML textbox. The boxes
omit an autofit directive, so only their authored placement establishes off-paper text.
Five documents include a paragraph-format revision; two controls omit the revision.

| Case | Visible textbox labels | Baseline balloon export | Review sheet |
| --- | ---: | --- | --- |
| Beyond right edge | 0 | Missing-fragment refusal | [Full page](markup-paper-clip-right.png) |
| Beyond left edge | 0 | Missing-fragment refusal | [Full page](markup-paper-clip-left.png) |
| Below paper, paragraph-relative | 0 | Missing-fragment refusal | [Full page](markup-paper-clip-paragraph-foot.png) |
| Box crosses foot; first label remains visible | 1 | Missing-fragment refusal | [Full page](markup-paper-clip-partial-foot.png) |
| On-paper box with balloons | 3 | Pass | [Full page](markup-paper-clip-visible-control.png) |
| Right-edge box without revision | 0 | Pass | [Full page](markup-paper-clip-right-control.png) |
| Paragraph-relative box without revision | 0 | Pass | [Full page](markup-paper-clip-paragraph-foot-control.png) |

Balloon companions improve from **3/7 baseline passes to 7/7 candidate passes**.
All seven input packages have zero Open XML SDK validation errors. Revised inputs declare
primary markup/hidden profiles; controls without revisions use final/hidden. All have
eligible native LibreOffice references, with complete visible inventories and declared
label regions. Native captures retain revision tint and margin marks; they do not accept
revisions or represent Word All Markup. Balloon companions use the separate existing
contract: exact source-label counts, forbidden hidden labels, printed dark ink, physical
paper bounds and a formatting-balloon label where requested. Native layout is
not a geometry oracle for All Markup. Word Online was unavailable; no Word parity is claimed.

Baseline `643357cda97027b16260b3ba20ff85ef59eb7406` has the same complete source tree as
merged main `81f99d8b7898ef620a52b344e7f86281f4356d74`. Candidate
`b5914103b16c9bbd0ee92a87b90d176933e919c9` is a clean production AOT build. Both use
strict font verification and the recorded sandboxed system Chromium. These are targeted
public-API diagnostics, without a pinned-runtime fidelity score or full-suite claim.

[Evidence](evidence.json) binds inputs, native references, both renderers, full reports,
PDF inspections and every full-page screenshot to hashes. `Compose.py` checks clean
source revisions, all recorded build files and runtime assets, declared companion
profiles, source-clipping warnings and every source label. Failed baseline exports have
explicit empty panels. Mutation tests remove source or balloon labels, reveal hidden
text, move text outside the sheet, and remove measured ink; each fails its existing
contract check without changing tolerances.

```sh
python3 docs/results/markup-paper-clips/Compose.py RUN BASELINE_SOURCE CANDIDATE_SOURCE
```

The shared diagnostic capture helper now forwards the declared markup options, as the
benchmark adapter already does. The fixtures import no renderer helper or document.
The prior 826 input bytes and declarations remain unchanged except for the generator
provenance hash. Issue #1558 remains open for other pagination and textbox failures.
