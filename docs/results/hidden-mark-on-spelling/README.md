# A hidden paragraph mark spelled `on` (Docxodus #1786)

`core-v175` adds an original Rowan pair. In `hidden-mark-on-spelling` the first paragraph's mark is hidden with
`<w:vanish w:val="on"/>`, which ST_OnOff allows; in the control, `hidden-mark-on-spelling-one-control`, it is hidden
with `w:val="1"`. A hidden paragraph mark joins its paragraph to the next, so `RowanTail` follows `RowanLead` on
one line in both. A `marker-reference-position` check pins `RowanTail` to the reference's position.

This is a code-level finding, not a measured render: Docxodus main `6c98b822` read `on` as off in its HTML
converter (`GetBoolProp`), so its HTML kept the two paragraphs apart while the control joined them, as Docxodus's
own test of the converter shows; the fix is [JSv4/Docxodus#1792](https://github.com/JSv4/Docxodus/pull/1792), merged as
`fba59965`. LibreOffice 25.8.7.3 joins both variants, with `RowanTail` at the same position, so the
1.5pt reference-position check tells a joined line from a separate one. New reference registration and full-suite
scoring for `core-v175` remain pending, and no reference application capture was made for this pair.
