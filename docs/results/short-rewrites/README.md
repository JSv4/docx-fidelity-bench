# Positional short paragraph rewrites

The requested #1556 review policy keeps each complete old sentence beside its positional
replacement. This intentionally supersedes the arrangement expectation for the four short
#1535 cases; their source and resolved endpoint bytes remain unchanged. Historical #1535
screenshots and measurements are preserved in [complete rewrites](../complete-rewrites/README.md).
Long-rewrite controls retain the coherent-block policy.

Twelve focused cases improve from **6/12** on baseline `3a958cc5` to **12/12** on candidate
`852c1bc4`; authored calibration also passes all twelve. All 24 LibreOffice endpoint
comparisons apply in each run. Independent exact markup endpoints, SDK validation,
whole-sentence pairing and selective consensus attribution remain mandatory. These are
focused diagnostics, not a complete 258-case suite score or a Word Compare parity claim.

Four existing Cedar inputs cover articles, literal ordinals, linked words and distinct prose.
Four new long counterparts require coherent side blocks. Independent Myrtle prose covers a
short two-paragraph rewrite, interior and unequal-count controls, and identical-reviewer
consensus credited once to the first reviewer. The second reviewer's selective view remains
the base, as declared by the default consensus policy.

Metric contract 22 adds `positional-rewrites` v1. Mutation tests preserve exact accepted and
rejected views while constructing whole-side blocks, wrong partners and alternating linked
words; all fail the arrangement assertion. A coherent old/new pair in a shared paragraph
passes. `revision-blocks` v1 is unchanged.

Each sheet contains every native review page, rendered by LibreOffice at 96 DPI, with
baseline, authored and candidate labels. `Compose.py` verifies every PDF's complete token
inventory against its unchanged redline and records source, PDF and raster hashes. The
source-bound adapter records, environment, case checks and SDK findings are in `evidence.json`.
The public WASM entry point is validated separately in the core PR.

### complete-rewrite-articles

![redline-complete-rewrite-articles: LibreOffice baseline, authored and candidate](redline-complete-rewrite-articles.png)

### complete-rewrite-numbered

![redline-complete-rewrite-numbered: LibreOffice baseline, authored and candidate](redline-complete-rewrite-numbered.png)

### complete-rewrite-linked

![redline-complete-rewrite-linked: LibreOffice baseline, authored and candidate](redline-complete-rewrite-linked.png)

### complete-rewrite-distinct-control

![redline-complete-rewrite-distinct-control: LibreOffice baseline, authored and candidate](redline-complete-rewrite-distinct-control.png)

### complete-rewrite-long-articles

![redline-complete-rewrite-long-articles: LibreOffice baseline, authored and candidate](redline-complete-rewrite-long-articles.png)

### complete-rewrite-long-numbered

![redline-complete-rewrite-long-numbered: LibreOffice baseline, authored and candidate](redline-complete-rewrite-long-numbered.png)

### complete-rewrite-long-linked

![redline-complete-rewrite-long-linked: LibreOffice baseline, authored and candidate](redline-complete-rewrite-long-linked.png)

### complete-rewrite-long-distinct-control

![redline-complete-rewrite-long-distinct-control: LibreOffice baseline, authored and candidate](redline-complete-rewrite-long-distinct-control.png)

### short-rewrite-pair

![redline-short-rewrite-pair: LibreOffice baseline, authored and candidate](redline-short-rewrite-pair.png)

### short-rewrite-interior-control

![redline-short-rewrite-interior-control: LibreOffice baseline, authored and candidate](redline-short-rewrite-interior-control.png)

### short-rewrite-unequal-control

![redline-short-rewrite-unequal-control: LibreOffice baseline, authored and candidate](redline-short-rewrite-unequal-control.png)

### short-rewrite-consensus

![redline-short-rewrite-consensus: LibreOffice baseline, authored and candidate](redline-short-rewrite-consensus.png)

