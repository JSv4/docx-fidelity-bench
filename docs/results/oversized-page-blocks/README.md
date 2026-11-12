# Oversized blocks and required final paragraphs (#1202)

A 400pt exact row cannot fit on a 160pt card. Main rejects its intentional overflow; nested tables
and bordered paragraph groups also fail instead of breaking across pages. Native Word captures
adjudicate clipping at the physical paper edge, the page following an oversized exact header,
and the required final paragraph after a table.

`core-v66` adds 13 independent benchmark cases. Six come from the unpublished row-geometry
branch; two of those receive schema-order corrections before their first registration. Seven
new cases cover paper-edge text, soft wrapping, footer overlap, header controls, and empty final
pages. All 1,012 prior DOCX files remain byte-identical. The renderer's own 23 regression probes
are additional diagnostic evidence and are not imported into the independent generator.

The [native capture record](native-word.json) preserves exact source/PDF hashes, complete raw
word geometry, every physical page (including empty ones), font identities, capture method and
font contract. All 13 captures pass their declared Word checks. Raw native PDF/DOCX bytes and
UI capture metadata remain in the durable local fixture cache. Cloud build information is
unavailable and recorded as null. Fonts are provisioned separately; binaries are not committed.

The labelled sheets show all pages at the same physical scale: native Word, unchanged main
(e7f96c00, whose tree equals merge 0895d935), and the fix. Actual export failures appear as
failures in the main panel. These are unscored public-export diagnostics: the host's formal
benchmark preflight requires unprivileged user namespaces, which are unavailable. The actual
Chromium 143 browser uses its sandbox and the existing root-owned helper. No preflight or
metric threshold was relaxed, and no full Word raster score is claimed.

The required final paragraph uses normal paragraph defaults, rather than the one-twip
structural paragraph used inside a nested cell. The 110pt control fits on one page; the 130pt
and exact-24pt-default-line controls end with a blank second page. Tests check every native
physical page, crop box and exact per-page word multiset. The 95 browser regression checks
passed at renderer 1fbc4a10; the next renderer commit changes only nested-cell test selectors.

Adversarial review corrected the omitted blank pages, rejected hidden Cedar11/Cedar12 as
optional visible tokens, retained Word's fourth page after the oversized header, and found
an unlinked footer part in a new probe. That footer was linked and freshly captured; its prior
unlinked capture stays diagnostic. Repeated footer tokens remain in the complete inventory;
region assertions use unique markers as required by the existing checker. Negative tests reject
missing blank pages, hidden-word leakage and moving MapleAfter back to page three.

All 13 candidate PDFs match native Word page count, physical geometry, font family and visible
text. Nine pass every mandatory Word check. Four retain glyph-origin failures under their original
0.5pt reference-position assertions: exact-400pt, the fitting exact-100pt control, the oversized
header and the nested table. For example, Cedar01 in the fitting control starts at y=28.226725pt
in Word and y=27.702208pt in both unchanged main and the fix. These failures are recorded in
[the raw candidate checks](benchmark-probes/evidence.json); tolerances remain unchanged.

## Independent benchmark cases

- [paragraphs-border-group-taller-than-page-times-new-roman](benchmark-probes/paragraphs-border-group-taller-than-page-times-new-roman.png)
- [paragraphs-border-taller-than-page-times-new-roman](benchmark-probes/paragraphs-border-taller-than-page-times-new-roman.png)
- [tables-final-exact-row-blank-page-times-new-roman](benchmark-probes/tables-final-exact-row-blank-page-times-new-roman.png)
- [tables-final-header-row-blank-page-times-new-roman](benchmark-probes/tables-final-header-row-blank-page-times-new-roman.png)
- [tables-header-row-taller-than-page-times-new-roman](benchmark-probes/tables-header-row-taller-than-page-times-new-roman.png)
- [tables-nested-row-taller-than-page-times-new-roman](benchmark-probes/tables-nested-row-taller-than-page-times-new-roman.png)
- [tables-row-exact-paper-edge-footer-times-new-roman](benchmark-probes/tables-row-exact-paper-edge-footer-times-new-roman.png)
- [tables-row-exact-paper-edge-lines-times-new-roman](benchmark-probes/tables-row-exact-paper-edge-lines-times-new-roman.png)
- [tables-row-exact-paper-edge-soft-wrap-times-new-roman](benchmark-probes/tables-row-exact-paper-edge-soft-wrap-times-new-roman.png)
- [tables-row-exact-taller-than-page-control-times-new-roman](benchmark-probes/tables-row-exact-taller-than-page-control-times-new-roman.png)
- [tables-row-exact-taller-than-page-times-new-roman](benchmark-probes/tables-row-exact-taller-than-page-times-new-roman.png)
- [tables-row-oversized-no-header-times-new-roman](benchmark-probes/tables-row-oversized-no-header-times-new-roman.png)
- [tables-row-oversized-two-hundred-times-new-roman](benchmark-probes/tables-row-oversized-two-hundred-times-new-roman.png)

## Additional core probes

- [bordered-paragraph-36](core-probes/bordered-paragraph-36.png)
- [bordered-paragraph-400](core-probes/bordered-paragraph-400.png)
- [exact-row-36](core-probes/exact-row-36.png)
- [exact-row-400](core-probes/exact-row-400.png)
- [header-row-36](core-probes/header-row-36.png)
- [header-row-400](core-probes/header-row-400.png)
- [nested-table-36](core-probes/nested-table-36.png)
- [nested-table-400](core-probes/nested-table-400.png)
- [tables-row-exact-taller-than-page-times-new-roman](core-probes/tables-row-exact-taller-than-page-times-new-roman.png)
- [tables-row-exact-taller-than-page-control-times-new-roman](core-probes/tables-row-exact-taller-than-page-control-times-new-roman.png)
- [tables-header-row-taller-than-page-times-new-roman](core-probes/tables-header-row-taller-than-page-times-new-roman.png)
- [tables-nested-row-taller-than-page-times-new-roman](core-probes/tables-nested-row-taller-than-page-times-new-roman.png)
- [paragraphs-border-taller-than-page-times-new-roman-schema-order-corrected](core-probes/paragraphs-border-taller-than-page-times-new-roman-schema-order-corrected.png)
- [paragraphs-border-group-taller-than-page-times-new-roman-schema-order-corrected](core-probes/paragraphs-border-group-taller-than-page-times-new-roman-schema-order-corrected.png)
- [exact-row-twelve-lines](core-probes/exact-row-twelve-lines.png)
- [exact-row-twelve-lines-footer](core-probes/exact-row-twelve-lines-footer.png)
- [header-after-repeat](core-probes/header-after-repeat.png)
- [header-two-hundred-points](core-probes/header-two-hundred-points.png)
- [tall-first-row-without-header](core-probes/tall-first-row-without-header.png)
- [exact-row-soft-wrapped-text](core-probes/exact-row-soft-wrapped-text.png)
- [table-end-row-110](core-probes/table-end-row-110.png)
- [table-end-row-130](core-probes/table-end-row-130.png)
- [table-end-default-line-24](core-probes/table-end-default-line-24.png)
