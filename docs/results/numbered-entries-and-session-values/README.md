# Numbered entries, saved calendar days and nested list labels

Eight independently authored fixtures exercise three public behaviors. The linked PNGs include the renderer and case ID. [Machine-readable observations](observations.json).

| Case | Baseline | Candidate or control |
| --- | --- | --- |
| [Numbered entry inserted](redline-numbered-entry-insert.png) | Default alignment tracks unchanged prose and misses the three in-place label edits. | The opt-in threshold preserves the prose and tracks R3→R4, R4→R5 and R5→R6. |
| [Numbered entry removed](redline-numbered-entry-remove.png) | Default alignment misses the in-place label edits. | All three edits occur in retained paragraphs. |
| [Numbered entry appended](redline-numbered-entry-append-control.png) | Passes at default settings. | Passes at default settings. |
| [Calendar day](calendar-date.png) | A Tokyo host stores June 17 as June 16 at 15:00 UTC. | Stores June 17 at midnight UTC. Writer displays the same date for both. |
| [Local timestamp](calendar-timestamp-control.png) | 01:30 JST stores 16:30 UTC on the previous day. | Same instant and explicit display text. |
| [Adjacent list starts](nested-adjacent-starts.png) | The first children receive flat labels 8 and 9. | Matches Writer’s 7.8 and 7.9. |
| [Implicit list parent](nested-implicit-parent.png) | Flat labels 8 and 9. | Matches Writer’s 7.8 and 7.9 without a physical parent paragraph. |
| [Child start of one](nested-start-one-control.png) | Matches Writer. | Same five labels. |

## Measurement

The baseline is Docxodus `965c3fde777487b936fb43ddd5bff93bd273ce16`. The complete projection track passed 38/41 there, 39/41 at the date fix `e0b33815e551c81ad5ae439ba4f95ec4f4b646f0`, and 40/41 at the independent list fix `8ce8c31dc638a89ab377d7d03df48b1f2ce7e283`. Each fix repaired only its corresponding failures. The other 36 cases passed on every build. The date probe runs the public string-based fill in a separate host with `TZ=Asia/Tokyo`. This track requires POSIX and the Tokyo zoneinfo entry. Each case checks the complete projected text and saved document schema as well as its declared calendar value or list labels.

For #1817, default redlines from the baseline were inspected with the new assertions. The insertion and removal cases request `minimumAnchorWordCount=2` on candidates supporting it. The append control uses the default. Both the independent authored redlines and the candidate `7d460f0e6eb6159c15bc03f48bfcb5820c1937ed` scored 100 on each of the three selected cases. This diagnostic includes independent markup resolution, LibreOffice 25.8.7.3 accept/reject, the Microsoft 365 schema validator and the declared assertions. A full redline suite score and desktop Word reference are outside these measurements.

Use `python3 -m bench.projection build` and `run` for the complete projection suite. For the comparison diagnostic, build the validator and redline adapter, then run `python3 -m bench redline run` with the three case IDs shown above (prefix each with `redline-numbered-entry-` and use suffixes `insert`, `remove` and `append-control`). The reference column shows the independently authored OOXML redline. The other redline columns show actual Docxodus output rendered by Writer.
