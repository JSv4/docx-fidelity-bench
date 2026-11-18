# A hidden paragraph mark spelled `on` (Docxodus #1786)

`core-v175` adds an original Rowan pair. In `hidden-mark-on-spelling` the first paragraph's mark is hidden with
`<w:vanish w:val="on"/>`, which ST_OnOff allows; in the control, `hidden-mark-on-spelling-one-control`, it is hidden
with `w:val="1"`. A hidden paragraph mark joins its paragraph to the next, so `RowanTail` follows `RowanLead` on
one line in both. A `marker-reference-position` check pins `RowanTail` to the reference's position.

Docxodus main `6c98b822` read `on` as off in its HTML converter, so its render kept `RowanLead` and `RowanTail` in two
paragraphs, while the control joined them; with the fix ([JSv4/Docxodus#1792](https://github.com/JSv4/Docxodus/pull/1792))
both join. These are Docxodus observations, not registered references: new reference registration and full-suite
scoring for `core-v175` remain pending, and no reference application capture was made for this pair.
