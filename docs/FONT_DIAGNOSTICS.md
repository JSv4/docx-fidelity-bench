# Actual font observations

This unweighted lane checks Docxodus #1525. It never changes the PDF/redline score denominator,
reference eligibility, strict font policy or verified environment contract. Missing requested
fonts legitimately remain missing and unverified even when Chromium paints fallback glyphs.

Seven original Birch fixtures cover a used missing face, a configured face, unused style and
font-table declarations, mixed Latin/CJK/emoji fallback, and distinct requested families on
separate pages. Each page has exactly one requested family and no generated labels or stories.
That separation lets Poppler's independently extracted per-page PDF font names check the
reported request-to-face association. Only a valid six-uppercase-letter PDF subset prefix is
removed. Mixed fallback must report both a configured face and system faces. Names do not
identify or attest font files; the report must say that file identity is unavailable.

The harness also checks complete per-page PDF character inventories, positive dark text paint,
page bounds, delivered HTML text, source/fragment/page associations, resolver status and warnings,
and report/artifact/digest bindings. A separate script-disabled HTML reader inventories every
text node; print and screen observations must each match its complete source/text identity multiset.
PDF character inventory ignores extraction order because
different fallback faces can occupy separate PDF text objects. It does not assess reading order.
Screen-only and print observations are checked separately against these fixed-layout fixtures.
Negative tests reject missing or changed faces, swapped request/page identities, erased warnings,
promoted verification, fabricated file evidence, removed text/paint and changed bindings.

The input packages contain no font programs. Provision Liberation Sans/Serif separately and
Noto CJK/emoji as system fallback fonts. `BENCH_FONT_DIRECTORY` selects the Liberation directory;
the default is `/usr/share/fonts/truetype/liberation2`. `DOCXODUS_CHROMIUM_PATH` optionally selects
a sandboxed Chromium executable. The run records configured font hashes, system font catalog,
browser executable hash, measurement tool identities, production source/build and fixture hashes.

```sh
python3 -m bench build-docxodus --source /path/to/Docxodus --commit FULL_SHA
python3 -m bench redline build-validator --out runs/font-validator
python3 -m bench.fonts --source /path/to/Docxodus --commit FULL_SHA --validator runs/font-validator --output runs/font-candidate
```

The output directory must be new. It contains raw public HTML/PDF/report artifacts, independent
PDF facts, page screenshots and per-case checks. A baseline without observations fails the new
diagnostic checks; existing resolver, content and geometry controls can still pass. No weighted
fidelity score is assigned. The existing `render.yml` workflow's `fonts` track runs exact baseline
and candidate revisions in the same provisioned environment and preserves all evidence.
