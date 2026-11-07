# Oversized body paragraphs with keep-next

Seven original Rowan documents isolate the impossible body keep in
[Docxodus #1558](https://github.com/JSv4/Docxodus/issues/1558). They use 11pt Liberation
Serif, 18pt exact spacing and a 648pt Letter body. Every label has a declared page and
18pt line band; fitting and unkept controls distinguish fragmentation from ignoring keeps.
The PDF profile is final/hidden, and these inputs contain no revisions or comments.
Core public tests separately exercise markup/word/margin/balloons.

| Case | Native/candidate pages | Baseline | Review sheet |
| --- | ---: | --- | --- |
| Direct keep-next, 65 lines | 2 | Clipped-body refusal | [All pages](oversized-keep-next-direct.png) |
| Style-inherited keep-next, 65 lines | 2 | Clipped-body refusal | [All pages](oversized-keep-next-style.png) |
| Both keep settings, 65 lines | 2 | Clipped-body refusal | [All pages](oversized-keep-next-both.png) |
| Seven opening lines, then 65 kept lines | 3 | Clipped-body refusal | [All pages](oversized-keep-next-after-opening.png) |
| 72 kept lines; closing paragraph on page 3 | 3 | Clipped-body refusal | [All pages](oversized-keep-next-boundary.png) |
| Fitting kept pair moves to page 2 | 2 | Pass | [All pages](oversized-keep-next-fitting-control.png) |
| Unkept pair separates across pages | 2 | Pass | [All pages](oversized-keep-next-no-keep-control.png) |

The existing mandatory PDF checks pass for **2/7 baseline cases and 7/7 candidate
cases**. All seven LibreOffice references are eligible, and all seven input packages
have zero Open XML SDK validation errors. This is a targeted public-API diagnostic,
not a full-suite result or a visual fidelity score. Word Online was unavailable;
no Word parity is claimed.

Baseline `643357cda97027b16260b3ba20ff85ef59eb7406` has the same complete source tree
as merged main `81f99d8b7898ef620a52b344e7f86281f4356d74`. Candidate
`ea72ca7065c620a3f0a314718351eebf096478c3` is a clean, source-bound production AOT build.
Both captures require verified fonts and use the recorded system Chromium with its
sandbox enabled. This borrowed browser is not the benchmark adapter's pinned runtime.

[Evidence](evidence.json) binds each input, PDF, complete render report, native inspection,
browser environment and screenshot to hashes. `Compose.py` rechecks source commits,
trees, clean tracked state, all recorded build files and runtime assets. It verifies every
label in source order, page and line band, and preserves full 96-DPI page rasters in the
comparison sheets. Baseline failures have explicit empty panels. Contract mutations
remove a label, move it to another page, or shift it by one line; each fails the existing
checks without changing their tolerances.

```sh
python3 docs/results/oversized-keep-next/Compose.py RUN BASELINE_SOURCE CANDIDATE_SOURCE
```

The fixtures import no renderer helper or document. The prior 819 input bytes and
declarations are unchanged, except for the generator provenance hash. The issue remains
open for other pagination and source-textbox failures; this change covers ordinary body
paragraphs with an impossible keep-next constraint.
