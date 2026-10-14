# Equivalent-control LibreOffice references

The direct LibreOffice track captures each original fixture. LibreOffice 25.8.7.3 omits the legacy page-number blocks in the two inputs introduced by [PR #7](https://github.com/JSv4/docx-fidelity-bench/pull/7). Their missing numbers make those direct captures ineligible.

PR #7 also authored equivalent complex decimal PAGE controls and proved that each pair changes only the header number representation. The controls retain the run's italic styling and 12-point size, page layout, body content, section start, full token inventory, and placement assertions. The restarted section still requests Roman numbering; the explicit Arabic field switch preserves the decimal behavior required for a legacy page-number block.

## Register the paired captures

First capture every original input with the existing command. Then derive a separately named reference track from that immutable bundle:

    python3 -m bench reference libreoffice --out references/lo-direct
    python3 -m bench reference equivalent-controls --reference references/lo-direct/bundle.json --out references/lo-controls

The derived track is `libreoffice-equivalent-controls`. Its bundle records the source bundle identity, control-policy version and implementation hash, and the exact control input identity for every substitution. It retains the complete direct bundle and its original PDFs under `direct/`. The selected reference PDF is copied byte-for-byte from the already captured control.

Before registration and again before measurement, the harness verifies both DOCX digests, every package member, the permitted XML change, and the shared tokens, assertions, fonts, profile, and category. A different section start, number format, run style, source declaration, PDF, or policy fails validation. The two legacy inputs remain byte-identical to PR #7, and the Docxodus adapter always receives those original inputs.

Measure the production renderer normally:

    python3 -m bench run --reference references/lo-controls/bundle.json --adapter docxodus --candidate FULL_COMMIT_SHA --out runs/controls --gate report

The HTML and JSON evidence identify the paired reference source and link to the defective direct capture. The derived track has its own reference identity and cannot be relabeled as the direct LibreOffice track or compared with its records.

## Repeat the reference provider

Use `libreoffice-reference` to repeat the exact recorded source of each reference PDF:

    python3 -m bench run --reference references/lo-controls/bundle.json --adapter libreoffice-reference --candidate reference-calibration --out runs/controls-calibration --gate close

On the direct track this adapter repeats each original input. On the equivalent-control track it repeats the declared control for substituted cases. The ordinary `libreoffice` adapter continues to render original inputs, so it also exposes LibreOffice's own legacy-field omission when measured against control references.

All metrics, eligibility requirements, mandatory checks, and tolerances remain in force. Any unrelated missing reference or failing fixture assertion remains visible and prevents its relevant gate from passing. Word captures continue to use their distinct tracks.
