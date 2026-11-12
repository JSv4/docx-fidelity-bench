# Fixed-pitch exact-fit boundary

Four independently authored Alder/Birch documents exercise the remaining
[Docxodus #1564](https://github.com/JSv4/Docxodus/issues/1564) boundary. They request
12pt Liberation Mono without embedding fonts or importing product fixtures.
Related core PR: [Docxodus #1635](https://github.com/JSv4/Docxodus/pull/1635),
captured candidate commit `38cad37f3c2f32c860637e0396dc5906e0d82a0b`.
The PR was subsequently rebased to `5be602b1` to resolve a changelog conflict
with newly merged CI changes. Production sources and all exact-fit regression
files are identical across these two commits; the capture retains its original
commit/tree identity.

| Case | Mode / alignment | First line | Available width |
| --- | --- | --- | --- |
| legacy-exact | 14 / left | 65 characters | 468pt |
| modern-exact | 15 / justified | 65 characters | 468pt |
| indented-exact | 14 / left | 60 characters | 432pt after a 36pt indent |
| narrow-control | 14 / left | Last word moves to line two | 467.95pt |

The issue author already confirmed the original product reproducer's 65-character
Word result. These new benchmark inputs have no Word captures. Their expected
line choices exercise the bounded nearest-twip fixed-cell inference, not a claim
that Word universally rounds font advances. The raw Liberation Mono advance is
1229/2048 em; its inferred 12pt cell is 7.2pt. Glyph dimensions remain raw font
dimensions. Complete token inventory, page count, authored line regions and
glyph dimensions are checked. Mutations reject a moved last word, missing text,
shrunken glyphs, an extra blank page, wrong paper size and unpainted text.
Independent adversarial review exposed the missing paper/paint checks and the
need to bind every complete strict-font report to its input and expected profile;
these checks now run on every retained observation.

The baseline is unpublished development commit `7d1026ed`, not released main.
It has the previous fixed-pitch policy and separate mixed-font development work.
The left-aligned exact and indented cases fail there; modern justification already
fits through gap compression, and the one-twip-narrower control already wraps.
Both controls retain the same lines with at most 0.76pt coordinate difference.
Before/after PDFs, renderer-labeled screenshots and build/input/font hashes are
retained in this directory. Captures use the public export API and sandboxed
system Chromium; they are unscored and do not qualify a pinned browser runtime.

Regenerate inputs with `python3 -m bench.fixtures`. Build each exact external
renderer revision and retain its `.docx-bench-build.json`. Prepare an ignored
run folder with the focused manifest, `bench.environment.environment(['Liberation
Mono'])`, and baseline/candidate build records, then run:

```sh
node docs/results/export-reliability/Capture.mjs BASELINE_SOURCE RUN/manifest.json RUN/baseline RUN/environment.json --html
node docs/results/export-reliability/Capture.mjs CANDIDATE_SOURCE RUN/manifest.json RUN/candidate RUN/environment.json --html
python3 docs/results/fixed-pitch/Review.py RUN
python3 -m unittest discover -s tests -p 'test_fixed_pitch.py' -v
python3 -m bench validate
python3 -m bench.audit
```

The review script uses PyMuPDF and Pillow to compose the screenshots. Refresh
provenance after intentional edits with `bench.audit.record()`.
