# Equivalent-control LibreOffice references

The direct LibreOffice track captures each original fixture. LibreOffice 25.8.7.3 omits the legacy page-number blocks in the two inputs introduced by [PR #7](https://github.com/JSv4/docx-fidelity-bench/pull/7). Their missing numbers make those direct captures ineligible.

PR #7 also authored equivalent complex decimal PAGE controls and proved that each pair changes only the header number representation. The controls retain the run's italic styling and 12-point size, page layout, body content, section start, full token inventory, and placement assertions. The restarted section still requests Roman numbering; the explicit Arabic field switch preserves the decimal behavior required for a legacy page-number block.

[PR #12](https://github.com/JSv4/docx-fidelity-bench/pull/12) supplies an exact-height pair: `36pt` and `720` twips. LibreOffice 25.8.7.3 imports the unit value as 36 twips, making each row 0.025 inches high instead of 0.5 inches and clipping six expected words. The derived track uses the already captured `720`-twip control. Its proof checks all three `exact` row heights, changes only their values from `36pt` to `720`, and requires the entire remaining document XML and every other package part to match. The original unit-valued fixture, cell text, widths, borders, fonts, inventory, and 0.5-point last-row assertion are preserved.

## Reference eligibility checks declared assertions

A reference capture is eligible only when it passes the case's own mandatory checks: the complete visible token inventory, the declared font families, and every declared assertion. Reference-relative positions are satisfied trivially, but absolute regions and same-page groups are not. Registration records the failing checks as `ineligibleChecks`, and every run repeats the check before measuring. A capture that contradicts the fixture's declared layout is not used as the standard for candidates. It stays in the direct bundle as visible evidence.

## Unit-valued minimum row heights (bench #16)

LibreOffice 25.8.7.3 reads a unit-valued `w:trHeight` as a tiny twip value. In the direct captures of the `36pt`, `0.5in`, `1.27cm`, `12.7mm`, `3pc`, `3pi` and `25.075pt` `atLeast` fixtures, every table collapses: `Birch03` sits at Y=99.999pt instead of 146.699pt, and the 30-row point ledger fits on one page instead of two. Those captures still pass their own declarations because their only position check is reference-relative, so their failure is invisible to eligibility. These cases are therefore captured through whole-twip controls.

**`minimum-row-height-units-to-twips-v1`** applies to the six 36pt-equivalent forms and the multipage point ledger. The proof requires:
- every `w:trHeight` in the original to carry the same unit value with `w:hRule="atLeast"` and no other attributes;
- that value, computed exactly in decimal, to be a whole number of twips;
- the control to differ only by that number.

All six forms are exactly 720 twips, and they use `tables-row-height-twips` (or `tables-row-height-multipage-twips`). An inexact unit value, a different rule, or a mixed table is rejected.

**`minimum-row-height-nearest-twip-v1`** applies to `tables-row-height-fractional-pt`. Its value of 25.075pt is 501.5 twips and has no whole-twip form. LibreOffice lays rows out in whole twips: 501 and 502 twips put `Birch03` at 124.799 and 124.899pt, so no LibreOffice capture can represent the original exactly.
- The rule rounds half up to 502 twips, the existing `tables-row-height-fractional-twips` fixture.
- It records the displacement bound: 0.025pt per row, and at most 0.05pt for `Birch03` after two rows.
- It requires that bound to be no more than a tenth of the case's smallest reference-position tolerance (0.5pt).
- This reference is labeled `nearest-twip-control`, not `equivalent-control`, in the bundle and in the report. The 25.075pt candidate is still compared with it at full metric strength.

The original unit fixtures, their 0.5-point last-row assertions and the collapsed direct captures are preserved.

## Logical indentation without conflicting aliases (bench #18)

Each `paragraphs-indentation-*` inventory has one RTL paragraph that carries two pairs of edges: the logical `w:start`/`w:end` at the form's value (36pt or 12pt), and the legacy `w:left`/`w:right` at 1440 twips. ECMA-376 Part 4 §14.3.1.2 treats `left`/`right` as the transitional names of `start`/`end`, so assigning them different values leaves the paragraph width ambiguous.

The two renderers resolve the ambiguity differently:
- LibreOffice 25.8.7.3 uses the legacy pair. The logical paragraph then wraps onto four lines and pushes `FirstMarker` to Y=160.999pt.
- Docxodus uses the logical pair the fixture is named for (`LogicalMarker`).

LibreOffice does parse every unit form correctly: all six unit captures are word-for-word identical to the twip capture. The conflict alone explains the mismatch.

Two authored controls state only the logical edges: `paragraphs-indentation-twips-logical-only` (720) and `paragraphs-indentation-small-twips-logical-only` (240). The `logical-indentation-without-conflicting-aliases-v1` proof proceeds in three steps:
1. It rewrites every unit-valued indent of the original as exact whole twips. A value that is not a whole number of twips is rejected.
2. It requires exactly one logical indentation whose legacy aliases conflict on both edges, then removes those two aliases.
3. It requires the control to match the result. Every other package part, the tokens, the assertions and the fonts must be identical.

LibreOffice places the control's `FirstMarker` at Y=148.349pt. The nine original fixtures, their assertions and the direct captures are preserved.

**Adjudication is pending.** Word's precedence for this conflicting input has not been captured. This control does not establish that logical edges win in Word, and Docxodus's precedence was not changed to match it. A Word capture of the original fixtures will be registered on its own track and judged against the same assertions.

## Kept boundary merge (bench #17)

`tables-vmerge-boundary-merged` declares that `Entry11`, `Entry12` and `Entry13` stay together on one page. Rows 11–13 are joined by one vertical merge, and every row has `cantSplit`. LibreOffice 25.8.7.3 places row 11 on page 1 and rows 12–13 on page 2, so its direct capture fails the declared `same-page` assertion and is ineligible.

`tables-vmerge-boundary-merged-kept` is the authored control. It is the same ledger with `w:keepNext` on every paragraph of the merged rows except the last, the standard WordprocessingML way to say "keep this row with the next one". LibreOffice honors it and keeps rows 11–13 together on page 2.

The `vertical-merge-keep-with-next-v1` proof requires all of the following:
- exactly one table, with one contiguous vertical merge that starts on its first row;
- no `keepNext` anywhere in the original;
- empty paragraph properties on the merged rows;
- a control that differs only by `keepNext` on the paragraphs of the merged rows before the last.

Every other package part, the tokens, the assertions, the fonts, the profile and the category must match. The original fixture, its same-page assertion and the defective direct capture are all preserved. The Docxodus adapter still receives the original input.

How Word itself paginates this merge is not yet adjudicated. When a Word capture is registered, it is judged against the same original assertion.

## Register the paired captures

First capture every original input with the existing command. Then derive a separately named reference track from that immutable bundle:

    python3 -m bench reference libreoffice --out references/lo-direct
    python3 -m bench reference equivalent-controls --reference references/lo-direct/bundle.json --out references/lo-controls

The derived track is `libreoffice-equivalent-controls`. CI registers it for every run and calibrates it with the `libreoffice-reference` repeat adapter. Its bundle records the source bundle identity, control-policy version and implementation hash, and the exact control input identity for every substitution. It retains the complete direct bundle and its original PDFs under `direct/`. The selected reference PDF is copied byte-for-byte from the already captured control.

Before registration and again before measurement, the harness verifies both DOCX digests, every package member, the permitted XML change, and the shared tokens, assertions, fonts, profile, and category. A different section start, number format, run style, source declaration, PDF, or policy fails validation. The legacy and exact-height inputs remain byte-identical to PRs #7 and #12, and the Docxodus adapter always receives those original inputs.

Measure the production renderer normally:

    python3 -m bench run --reference references/lo-controls/bundle.json --adapter docxodus --candidate FULL_COMMIT_SHA --out runs/controls --gate report

The HTML and JSON evidence identify the paired reference source and link to the defective direct capture. The derived track has its own reference identity and cannot be relabeled as the direct LibreOffice track or compared with its records.

## Repeat the reference provider

Use `libreoffice-reference` to repeat the exact recorded source of each reference PDF:

    python3 -m bench run --reference references/lo-controls/bundle.json --adapter libreoffice-reference --candidate reference-calibration --out runs/controls-calibration --gate close

On the direct track this adapter repeats each original input. On the equivalent-control track it repeats the declared control for substituted cases. The ordinary `libreoffice` adapter continues to render original inputs, so it also exposes LibreOffice's own legacy-field omission when measured against control references.

All metrics, eligibility requirements, mandatory checks, and tolerances remain in force. Any unrelated missing reference or failing fixture assertion remains visible and prevents its relevant gate from passing. Word captures continue to use their distinct tracks.
