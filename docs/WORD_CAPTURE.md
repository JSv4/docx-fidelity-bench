# Word reference registration

Capture each exact input externally with Word's own PDF export, preserve the original PDF, and inspect it before import. Use the provider-neutral `word` track unless a capture route needs its own track; tracks are never mixed. Check that Word did not repair the input, alter fields or view settings, or substitute the declared font.

The JSON metadata must contain:

```json
{
  "track": "word",
  "rightsApproved": true,
  "capturedAt": "ISO 8601 timestamp",
  "provider": "Microsoft Word",
  "method": "PDF export",
  "reportedBuild": null,
  "platform": "Recorded browser and operating system",
  "profile": {"review": "final", "comments": "hidden"},
  "fontContract": {
    "LiberationSerif-Regular.ttf": {"family": "Liberation Serif", "sha256": "ACTUAL_SHA256"}
  },
  "cases": {
    "columns-continuous": {"inputSha256": "MANIFEST_SHA256", "pdfSha256": "CAPTURED_PDF_SHA256"}
  }
}
```

The font contract must include the actual regular, bold, italic, and bold-italic files, matching the harness environment. The example above is deliberately incomplete. Copy the exact `environment.fonts` object from the relevant reference bundle rather than fabricating font hashes. Record unavailable cloud build information as `null`. `rightsApproved` attests the operator's review of input, image, font embedding, and publication rights.

Supply PDFs named `CASE_ID.pdf`. Run `bench reference import` with the metadata file, PDF directory, and a new output directory. Source and PDF digests, view, font contract, PDF font identities, the complete visible token inventory and every declared assertion are checked. Missing cases remain pending. Import records capture facts; it does not establish that an operator's declared provider or build is authentic. Retain the operator-reviewed capture evidence with the bundle.

Import runs each capture through its case's own mandatory checks: the visible token inventory, the declared font families and every declared assertion, including Word-adjudicated ones. A capture that fails any of them is registered with `eligible: false` and its `ineligibleChecks`, kept as evidence and not used as a standard. A Word installation without the declared font substitutes another (for example a metric-compatible Times New Roman for Liberation Serif); such a capture fails `declared-font-families` and stays ineligible. Its layout can still inform declared assertions, but it cannot be scored against.

For `paragraph-contract-times-new-roman` (core-v34), capture the separately registered Times New Roman input, not a renamed PDF from `paragraph-contract`. The local font contract includes both families and all eight style files. The original Liberation Serif capture remains ineligible if Word substitutes Times New Roman, even when the new variant passes. Word is needed only for capture; registration, measurement and tests run offline.

Record any observed font-version difference with the capture evidence. Family eligibility is not proof of identical font binaries: the October 18, 2026 Word Online agreement capture embeds Times New Roman 7.11, while the local Core Fonts files are 2.82. The compared embedded glyph advances agree, but that does not establish identical outlines, kerning or rasterization. See the [agreement comparison](results/paragraph-contract-word.md).

## Word's embedded-font aliases

Word can emit an embedded TrueType font under an internal PDF name such as
`___WRD_EMBED_SUB_1434`. The name alone remains ineligible. An operator may qualify
that exact capture with `fontIdentityBindings` only after reviewing its used glyph
outlines, advances, bearings and instructions against the exact embedded source font.
Retain the audit and its digest with the capture. This is an operator attestation;
the harness verifies the cryptographic binding and does not repeat the outline audit.

Each case's binding list records `pdfFontName` (the unprefixed raw alias), `family`,
`sourceFontPart`, `sourceFontSha256`, `embeddedProgramSha256`, `glyphAuditSha256`, and
`reviewedGlyphIdentity: true`. Import checks that the family is declared by the case,
the source font table embeds that family through that part, the part's bytes match the
local font contract, and qpdf extracts exactly the audited native font-program bytes.
Duplicate, unknown, missing, substituted or unreviewed bindings fail. PDF font names,
coordinates and raster pixels are never renamed or normalized. Other unqualified fonts
remain ineligible. Every run repeats the source/program binding checks, and the reference
bundle binds the verifier's version and source hash.

An independently captured pack can supply an explicit manifest without changing the
existing authored corpus:

```sh
python3 -m bench reference import --manifest references/PACK/registry.json \
  --metadata references/PACK/metadata.json --pdf-dir references/PACK/native \
  --out references/PACK/registered
python3 -m bench run --manifest references/PACK/registry.json \
  --reference references/PACK/registered/bundle.json --adapter docxodus \
  --candidate FULL_SOURCE_SHA --out runs/word-candidate --gate mandatory
```

Pack inputs and generator hashes receive the same registry validation. Captured PDFs,
source inputs, separately licensed font parts, audits and registered bundles stay outside
the source inventory in ignored reference directories or pinned evidence assets. Their
publication rights and provenance must be explicit; the source repository does not acquire
font binaries by accepting an external manifest.

## Provider tracks and renderer profiles

Keep Word and LibreOffice bundles and accepted measurements separate. Run the previous
accepted renderer and the candidate against the same immutable bundle and compare within
that provider track. Scores from different tracks are not aggregated or compared as a
regression series. Case-specific Word adjudication must retain the LibreOffice findings
and link the verified Word evidence; it does not rewrite the LibreOffice reference.

Results now record `layoutProfile: "default"` in their measurement contract and display it
next to the reference track. This names the one existing renderer mode; it adds no public
layout option. Older records without that field retain the implicit default identity.
Comparison rejects different provider tracks or layout profiles, so future Word and
LibreOffice renderer modes must each establish and protect their own accepted results.
