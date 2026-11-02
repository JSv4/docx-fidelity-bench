# Actual font observations

Seven original Birch cases compare public exports from baseline `915d6fc1` and final candidate
`be7298ac` in pinned CI, with earlier local evidence at `ce7e470f`. These are source-bound,
unweighted diagnostics, with no native-reference or
fidelity-score claim. All baseline and candidate PDF page geometry, text coordinates and
font facts are identical. The candidate adds observed faces and source attribution; it
preserves missing-font warnings, resolver status and file-verification limits.

Each sheet shows every produced page and a text-detail crop. Baseline observations are
absent; the candidate observations match per-page font names independently read by Poppler.
The mixed-script case requires Liberation Sans plus CJK and emoji fallback. The two-page
cases independently test distinct request-to-face associations on each page.

[Local source/artifact bindings](local-evidence.json) identify the exact revisions and PDFs.
The benchmark checks both HTML-only screen observations and batch print observations,
complete text-node identities, page/report bindings, content inventories and positive text
paint. The final local candidate passes all seven cases; the baseline fails only new observation
checks. All nine page rasters are byte-identical. The [pinned CI run](https://github.com/JSv4/docx-fidelity-bench/actions/runs/41522064019)
also passes all seven cases at final candidate `be7298ac`, with identical baseline/candidate
PDF facts and all nine page rasters. Its 14 actual reports validate against the v2 schema.
[Pinned source/runtime and check evidence](pinned-evidence.json) records the measurement.
The final commit adds only the separately verified test-loader repair to `ce7e470f`.

The comparisons below show the pinned CI outputs. The original local comparisons and
[local bindings](local-evidence.json) remain available beside them.

## used-missing

![used-missing: baseline and candidate](production/used-missing.png)

## configured-control

![configured-control: baseline and candidate](production/configured-control.png)

## unused-style-control

![unused-style-control: baseline and candidate](production/unused-style-control.png)

## unused-table-control

![unused-table-control: baseline and candidate](production/unused-table-control.png)

## mixed-glyphs

![mixed-glyphs: baseline and candidate](production/mixed-glyphs.png)

## separate-requests

![separate-requests: baseline and candidate](production/separate-requests.png)

## missing-separate

![missing-separate: baseline and candidate](production/missing-separate.png)
