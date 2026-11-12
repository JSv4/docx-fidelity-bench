# Mixed minimum line spacing

Six original Primrose documents cover per-line minimum spacing and absolute
baselines for [Docxodus #1566](https://github.com/JSv4/Docxodus/issues/1566).
Related core PR: [Docxodus #1631](https://github.com/JSv4/Docxodus/pull/1631).
The documents use literal OOXML and independently provisioned Liberation Serif;
no product fixtures, helpers or font programs are imported.

| Case | Lines | Minimum | Large run | Pages |
| --- | ---: | ---: | --- | ---: |
| lead-13 | 18 | 13pt | First line, 20pt | 1 |
| tail-13 | 64 | 13pt | Last line, 20pt | 2 |
| lead-16 | 64 | 16pt | First line, 20pt | 2 |
| tail-16 | 18 | 16pt | Last line, 20pt | 1 |
| uniform-16-control | 18 | 16pt | None | 1 |
| natural-control | 18 | Single spacing | None | 1 |

Other runs are 10pt. A 103pt column fits one 20pt label or one 10pt label,
but not two small labels and their separating space. There are no hard breaks.
Independent font metrics give each label an advance of `10467 / 2048 × size`,
a natural line height of `2355 / 2048 × size`, and a glyph box height of
`2268 / 2048 × size`. Each line occupies the larger of its natural height and
the authored minimum. Complete lines fit into the 648pt body area.

The original issue-author Word PDF retained in the core PR's
`TestFiles/LineSpacingWord` places an enlarged minimum baseline at line height
minus natural descent. This corrects the earlier centering assumption in the
historical small-minimum diagnostic. Each new case asserts the resulting glyph
box inside a 0.76pt coordinate tolerance for Chromium's 0.75pt origin rounding,
with complete token inventory and page assignment. `Measurements.py` separately
requires exact total pages and source-sized glyph width/height within 0.1pt.
The contract test rejects missing words, a 2pt upward shift, shrunken glyphs and
an extra blank page. Independent adversarial review exposed the latter two
gaps in containment-only checks; both are now checked. These benchmark inputs have no Word
captures, and no new fidelity score or pinned-browser qualification is claimed.

`evidence.json` binds inputs, renderer commits and trees, build files, strict-font
contracts, PDFs and inspection facts. The baseline is unpublished development
commit `7d1026edf971338accbbeb3bff82953cd63e993c`, not released main. It also
contains separate horizontal-fitting work. The candidate is core PR #1631 at
`01037c930349e9f4c52cc970e48f371b2974df80`. The five minimum cases fail the
baseline's authored bounds and pass on the candidate. The natural control
passes both, with identical text and page inventory and a maximum coordinate
difference of 0.328125pt from the different horizontal-fitting path; it is not
pixel-identical. Every review sheet labels both renderers and includes the
complete narrow text column on every page. Full PDFs are retained in `pdf/`.

Regenerate fixture bytes with `python3 -m bench.fixtures`. To repeat the capture,
build the two exact external renderer revisions with `python3 -m bench
build-docxodus --source SOURCE --commit SHA`, then prepare an ignored run folder
with the decompressed `manifest.json.gz`, an environment record from
`bench.environment.environment(['Liberation Serif'])`, and copies of each
renderer's `.docx-bench-build.json` as `baseline-build.json` and
`candidate-build.json`. From the benchmark root run:

```sh
node docs/results/export-reliability/Capture.mjs BASELINE_SOURCE RUN/manifest.json RUN/baseline RUN/environment.json --html
node docs/results/export-reliability/Capture.mjs CANDIDATE_SOURCE RUN/manifest.json RUN/candidate RUN/environment.json --html
python3 docs/results/mixed-minimum/Review.py RUN
python3 -m unittest discover -s tests -p 'test_mixed_minimum.py' -v
python3 -m bench validate
python3 -m bench.audit
```

The review script additionally needs PyMuPDF and Pillow. Captures use a sandboxed
system Chromium, recorded by version and executable hash. Original captures
reused completed production builds whose artifact hashes were verified, as
recorded in their build recipes. After intentional repository changes, refresh
the provenance inventory with `python3 -c 'from bench.audit import record; record()'`.
