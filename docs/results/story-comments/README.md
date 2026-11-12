# Story-comment captures

These five original cases cover footer and footnote comments, with a body-comment control,
and a footer range beside a real body reference, with a body-reference control. The first
three reuse the existing `fixtures/story-comments` inputs at 8bbf090 byte-for-byte. No
product fixtures or third-party document content are imported.

The PDF track hides comments and retains the full document-token, page and raster checks.
Its delivered-HTML companion uses margin comments and requires each declared note body to
be readable. All five LibreOffice PDF references are eligible and calibrate at 100. The
focused bundle covers five of 291 cases, so it makes no full-suite score claim.

All five sheets were visually inspected. They show the hidden-comments LibreOffice
reference, followed by actual margin-profile Docxodus PDFs before and after the fix in
[Docxodus #1363](https://github.com/JSv4/Docxodus/pull/1363). The five full-page 96-dpi rasters
are neither cropped nor aligned. Before uses 26da6b87, whose tree equals base 45657239;
after uses 20dc43eb. The three reproducers fail the independent HTML readability checks
before and pass after; both controls pass in both versions. Margin notes keep their existing
document-order stacking rather than moving adjacent to each text anchor.

Local Docxodus exports use a caller-owned browser because this host cannot establish
Chromium's process sandbox. Both profiles pass strict font policy. They have
`browserObserved` verification and are **unmeasured for production scoring**. The normal
adapter policy remains unchanged. These are diagnostic readability checks, not eligible
production HTML measurements. The implementation's committed export tests retain sandboxing.

Microsoft's [implementation note](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/84a35ef3-9c12-4b59-ab4c-4a88f520d06c)
says OOXML permits non-body comment anchors but Word ignores them. This work implements
Docxodus's documented content-preservation contract; no Word presentation parity or new
Word capture is claimed. The fixtures omit non-body reference runs because LibreOffice
cannot load that shape; the product tests also cover real reference marks in all five stories.

SDK 3.5.1 reports only `Sem_MissingReferenceElement` semantic findings for these permitted
non-body anchors, despite each target id existing in the main document's comments part.
There are no schema findings. All six raw benchmark findings and all twelve findings from
the all-stories product fixture remain in `capture.json`; body controls have none. Actual
target IDs are verified, without a validator or adapter waiver. Source-bound builds, browser
identity, observer policy, reference/calibration contracts, PDF/HTML/raster/sheet hashes and
raw SDK findings are recorded there. All 938 prior DOCX files remain byte-identical.
