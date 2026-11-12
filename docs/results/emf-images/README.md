# Static EMF records and frame overflow

Eight original Iris cases pin the last missing content type in
[Docxodus #1554](https://github.com/JSv4/Docxodus/issues/1554). They add seven EMF
inputs and an ordinary PNG control, bringing the suite to core-v142 / 1,044 cases.
All 1,036 prior inputs and declarations are unchanged except generator provenance.
The authored records cover default cosmetic pens, explicit geometric pens,
rectangle and ellipse geometry, anisotropic picture sizing and frame overflow.
No product fixtures, helpers, documents or fonts were imported.

The production candidate is `61e3b623449d6d00dc2b9a99d126f84526d1c38e`, built with
the full public WASM and export builds and captured through the production adapter
with its pinned Chromium 143. Its source/tree, built-asset hashes, runtime, fonts,
input identities and complete render reports are retained in compressed evidence.
All eight exports pass the existing mandatory checks: complete tokens, fonts, page
geometry, blue paint bounds within 1.5pt, coverage within 8%, and receipt text
position within 1.5pt. No geometry tolerances were relaxed. Native public HTML
conversion on main `3cbf7fa7f2591cbb01191507e630140097bca2e6` produces a whole-image
placeholder for all seven EMFs; the PNG control renders. This baseline is native
HTML evidence, not a claim of a baseline production PDF run.

| Case | Production score | Reference |
| --- | ---: | --- |
| stock | 97.76 | Expanded-frame control |
| wide-stock | 98.06 | Expanded-frame control |
| expanded-stock | 97.76 | Direct |
| expanded-wide-stock | 98.06 | Direct |
| consistent | 96.10 | Direct |
| geometric | 82.69 | Direct |
| ellipse | 83.00 | Direct |
| png-control | 99.29 | Direct |

LibreOffice clips the two overflowing originals at the picture boundary. The
[explicit equivalence proof](../../REFERENCE_CONTROLS.md#emf-frame-overflow-docxodus-1554)
expands Frame and picture dimensions by exactly 5/4, leaving the mapping and all
paint coordinates unchanged. Only those values may differ; every other XML node,
EMF byte and package part must match. The carrier must be uncropped, unrotated,
nonwrapping and anchored at the same fixed page position. The original direct
captures remain in `pdf/*-direct.pdf`, and the text receipt is exactly unchanged
between each original/control LibreOffice capture. Mutation tests reject changes
to origin, dimensions, Frame, reference-device mapping, drawing records, crop,
rotation and wrapping. Repeating all eight recorded reference sources scores 100
and passes the close-match gate.

**Word adjudication is pending.** These results establish restored content and
physical record mapping, not complete Word or LibreOffice fidelity. Docxodus uses
one CSS pixel for cosmetic pens; LibreOffice prints a thinner hairline and adds a
VML picture outline. Blue-fill checks exclude that black outline. Two geometric
outline cases remain below the visual close-match threshold despite passing their
mandatory geometry checks. No complete visual-equivalence claim is made.

The initial unpublished PNG diagnostic used an interior rectangle. LibreOffice
recompressed it as JPEG, contaminating edge colors and failing the strict color
oracle; `diagnostic-v1` retains that input and both PDFs. The finalized control is
a uniform blue bitmap with stable full-frame geometry. The finalized bytes were
frozen before capture. The seven EMF fixture assertions were not weakened.

Each attached PNG shows a labeled page crop from direct LibreOffice, the selected
reference and production Docxodus. Full PDFs and inspected facts are retained.
`Review.py` verifies bindings and composes these sheets using PyMuPDF and Pillow.
The benchmark has no added runtime dependency on those review-only tools.

Reproduce with a focused manifest containing the eight `images-emf-*` cases and
its matching suite member list, then run:

```sh
python3 -m bench reference libreoffice --out references/emf --manifest runs/emf/manifest.json
python3 -m bench reference equivalent-controls --reference references/emf/bundle.json --out references/emf-controls --manifest runs/emf/manifest.json
DOCXODUS_SOURCE_ROOT=/path/to/exact/build python3 -m bench run --reference references/emf-controls/bundle.json --adapter docxodus --candidate FULL_SHA --out runs/emf/candidate --manifest runs/emf/manifest.json --gate mandatory
python3 -m bench run --reference references/emf-controls/bundle.json --adapter libreoffice-reference --candidate reference-calibration --out runs/emf/calibration --manifest runs/emf/manifest.json --gate close
python3 -m unittest discover -s tests -p 'test_emf_images.py' -v
```

`bench.audit.record()` refreshes the deliberate source/artifact inventory; run
`python3 -m bench.audit` afterward to verify deterministic inputs and provenance.
