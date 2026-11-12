# Text placement

Eleven original Hazel documents put the prose of the `paragraph-text-*` cases into a paragraph's
own structure. Word chooses justified lines and kerning per paragraph and per run, so each
placement must keep the line its plain control has. All text is 12 pt Liberation Serif in
compatibility mode 15, in the same 501 pt (justified prose) or 390 pt (kerning prose) text band.

| Case | Placement | Line 1 ends with |
| --- | --- | --- |
| `text-placement-justify-both-unspaced` | justified; no `w:spacing` anywhere | `landing` |
| `text-placement-justify-both-bold` | justified; `northern` bold | `landing` |
| `text-placement-justify-both-link` | justified; `harbor` in a hyperlink | `landing` |
| `text-placement-justify-both-list` | justified numbered item, 0.5 in hanging indent | `landing` |
| `text-placement-justify-both-cell` | justified, in a fixed cell with default 0.075 in margins | `landing` |
| `text-placement-justify-left-{bold,list,cell}` | left-aligned controls | `northern` |
| `text-placement-kern-left-bold` | `HazelTail` bold, no `w:kern` | `Warm` |
| `text-placement-kern-left-zero` | `w:kern w:val="0"` | `Warm` |
| `text-placement-kern-left-at-size` | `w:kern w:val="24"` on 12 pt text | `Water` |

The band is widened by the list item's indent, or by the cell's margins, so the text band never
changes. Independent advances, as in `paragraph-text-*`: the justified prefix is 502.107421875 pt,
so Word condenses its spaces to keep `landing`. Bold `northern` adds 5.34375 pt, and condensing
still strains less than stretching the 463.11328125 pt line without `landing`. The kerning prefix
is 395.173828125 pt unkerned and 384.685546875 pt kerned in its 390 pt band.

**Native evidence.** Word 2024 opened copies of all eleven inputs, plus both plain controls, with
Liberation Serif renamed to its metric twin Times New Roman. Each word's line was read with
`Range.Information`, and every case above ended its first line exactly as listed. Word treats
`w:kern w:val="0"` as kerning off. ECMA-376 17.3.2.19 would read it as a minimum of zero, so the
case pins Word. The same measurements on the Docxodus issue fixtures are recorded in
[#1550](https://github.com/JSv4/Docxodus/issues/1550#issuecomment-6769216295) and
[#1562](https://github.com/JSv4/Docxodus/issues/1562#issuecomment-6769226140).

**Pending.** This Windows capture host has no pinned LibreOffice, so no reference bundle,
eligibility record, baseline or candidate score, or retained PDF is included here yet. Native
references and labeled screenshots remain to be added on a capture host. All 1084 prior inputs
and declarations are unchanged apart from generator provenance.

`tests/test_text_placement.py` checks that each case keeps its control's text and that the
boundary word is assigned to the line Word measured.

## Reproduction

```sh
python3 -m bench validate
python3 -m unittest discover -s tests -v
python3 -m bench.audit
```
