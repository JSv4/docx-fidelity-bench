# Independent review visibility

These 14 original Hazel fixtures exercise Docxodus #1523: formatting-only, comment-only,
and combined controls, followed by every formatting/text/comment visibility combination.
Each pair uses identical source bytes. All 724 previous corpus inputs are unchanged.

The first panel is a separately captured LibreOffice primary PDF, with comments hidden.
Mixed-revision primary PDFs show both old and new text, matching LibreOffice's native
view; the other primary PDFs use the final view. The middle and right panels are the
candidate's default and requested review display. Each sheet includes the complete page
and a crop around the text and review labels. This does not claim native Word balloon
geometry or a before/after renderer comparison.

Local checks pass for all 14 cases: exact source inventories and positive dark paint in
printed companions; absent hidden-source/formatting tokens; accessible HTML text; exact
balloon, insertion, deletion and markup-container counts; original package digest; and no
derived source package. Positive formatting cases also require the printed `Formatted:`
label. The same-file comment-only control preserves its display when formatting is hidden.
All 14 fixtures pass Open XML SDK 3.5.1 validation. The independent browser observer is
mutation-tested for missing and duplicated families, retained empty containers and hidden
source markers. Final adversarial review added complete visible HTML token inventories
and forbidden tokens; mutations now catch empty/hidden comment text and comments leaked
as plain paragraphs independently of the companion PDF.

[Local evidence and source identity](local-evidence.json) and [schema findings](schema.json)
record the observed artifacts. Pinned production benchmark runs are pending; these local
checks do not constitute a full-corpus fidelity score.

## review-visibility-format-only-default-control

![review-visibility-format-only-default-control: LibreOffice primary, candidate default and requested review display](review-visibility-format-only-default-control.png)

## review-visibility-format-only-hide-formatting

![review-visibility-format-only-hide-formatting: LibreOffice primary, candidate default and requested review display](review-visibility-format-only-hide-formatting.png)

## review-visibility-comment-format-default-control

![review-visibility-comment-format-default-control: LibreOffice primary, candidate default and requested review display](review-visibility-comment-format-default-control.png)

## review-visibility-comment-format-hide-formatting

![review-visibility-comment-format-hide-formatting: LibreOffice primary, candidate default and requested review display](review-visibility-comment-format-hide-formatting.png)

## review-visibility-comment-only-default-control

![review-visibility-comment-only-default-control: LibreOffice primary, candidate default and requested review display](review-visibility-comment-only-default-control.png)

## review-visibility-comment-only-hide-formatting

![review-visibility-comment-only-hide-formatting: LibreOffice primary, candidate default and requested review display](review-visibility-comment-only-hide-formatting.png)

## review-visibility-mixed-000

![review-visibility-mixed-000: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-000.png)

## review-visibility-mixed-001

![review-visibility-mixed-001: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-001.png)

## review-visibility-mixed-010

![review-visibility-mixed-010: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-010.png)

## review-visibility-mixed-011

![review-visibility-mixed-011: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-011.png)

## review-visibility-mixed-100

![review-visibility-mixed-100: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-100.png)

## review-visibility-mixed-101

![review-visibility-mixed-101: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-101.png)

## review-visibility-mixed-110

![review-visibility-mixed-110: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-110.png)

## review-visibility-mixed-default-control

![review-visibility-mixed-default-control: LibreOffice primary, candidate default and requested review display](review-visibility-mixed-default-control.png)
