# Word reference registration

Word references are pending in the initial corpus. Capture each exact input externally with Word Online PDF export, OneDrive PDF conversion, or licensed desktop Word. Record each provider as a distinct track, preserve the original PDF, and inspect it before import. Check that Word did not repair the input, alter fields or view settings, or substitute the declared font.

The JSON metadata must contain:

```json
{
  "track": "word-online",
  "rightsApproved": true,
  "capturedAt": "ISO 8601 timestamp",
  "provider": "Microsoft Word Online",
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

Supply PDFs named `CASE_ID.pdf`. Run `bench reference import` with the metadata file, PDF directory, and a new output directory. Source and PDF digests, view, font contract, PDF font identities, and the complete visible token inventory are checked. Missing cases remain pending. Import records capture facts; it does not establish that an operator's declared provider or build is authentic. Retain the operator-reviewed capture evidence with the bundle.
