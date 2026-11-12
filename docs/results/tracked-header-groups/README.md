# Tracked header groups — Docxodus #1045

Four authored Juniper fixtures retain the native DrawingML and revision wrappers. In LibreOffice
25.8.7.3, insertion and deletion of an anchored header group fail during import; the identical
plain group and a tracked single textbox render. All four inputs have zero Open XML SDK 3.5.1
Microsoft365 validation errors. The original DOCX bytes were preserved in every conversion.

| Case | LibreOffice 25.8.7.3 | Word Online PDF capture |
|---|---|---|
| Inserted group | Application error; no PDF | Three labels and receipt |
| Deleted group | Application error; no PDF | Receipt only; deleted group omitted |
| Plain group control | PDF | Three labels and receipt |
| Inserted single textbox control | PDF | One label and receipt |

[LibreOffice observations](libreoffice.json) retain the source hashes, renderer version, failure
codes, and preservation checks. [Word capture metadata](word-captures.json) records source/PDF/PNG
hashes, extraction, fonts, and the actual export route. Captures were made on 2026-11-04 using
Chrome and the signed-in Word Online UI through Playwright. No changes were accepted or rejected.

These are diagnostic captures, **not registered reference PDFs or fidelity scores**. The Word
Online export did not expose the deleted drawing even with “Download as PDF with comments.”
The deletion fixture deliberately retains the complete markup token inventory; weakening that
inventory to match this capture would conceal missing content. The other captures also do not
establish a matching markup/font contract. Full reference eligibility remains pending.

The matching Docxodus repair reports a specific static LibreOffice compatibility risk through
the shipped deliverable verifier, including on newly produced comparison output. It preserves
the native package and directs callers to a renderer verified for their document. These cases
pin the underlying rendering failure and controls for future scoring; they do not claim that
LibreOffice itself has been repaired.

## Word Online diagnostic screenshots

Inserted group, PDF export:

![Inserted group — Word Online](tracked-header-group-inserted.word.png)

Deleted group, PDF export with comments. The absent labels make this capture unsuitable as a
reference for the fixture's markup profile:

![Deleted group omitted — Word Online](tracked-header-group-deleted.word.png)

Plain group control, PDF export:

![Plain group — Word Online](tracked-header-group-plain-control.word.png)

Inserted single textbox control, PDF export:

![Single textbox — Word Online](tracked-header-group-single-control.word.png)
