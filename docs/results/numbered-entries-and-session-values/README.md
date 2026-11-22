# Numbered entries, saved calendar days, nested list labels and cached reference results

Fifteen independently authored fixtures exercise four public behaviors. The reference column is a desktop
word processor (build 16.0.20326) on Windows 11 at UTC−06:00; its observations are in
[reference.json](reference.json). Measured Docxodus values are in [observations.json](observations.json). The
linked PNGs are LibreOffice Writer 25.8.7.3 views made before this revision, and include the renderer and case ID.

| Case | Baseline | Candidate or control | Desktop word processor (build 16.0.20326) |
| --- | --- | --- | --- |
| [Numbered entry inserted](redline-numbered-entry-insert.png) | Default alignment tracks unchanged prose and misses the three in-place label edits. | The opt-in threshold preserves the prose and tracks R3→R4, R4→R5 and R5→R6. | Its own compare tracks no description and reports no move. Each renumbered label is a deleted and an inserted label paragraph at word level (its default), and an in-place digit edit, `R[3→4]`, at character level. |
| [Numbered entry removed](redline-numbered-entry-remove.png) | Default alignment misses the in-place label edits. | All three edits occur in retained paragraphs. | As above, in the other direction. |
| [Numbered entry appended](redline-numbered-entry-append-control.png) | Passes at default settings. | Passes at default settings. | One insertion: the new label and entry. |
| `redline-reference-result-simple` | The whole sentence around the field is deleted and inserted again. | Only `16.4` → `21.8` is tracked, in the field's result. | Only `16.4` → `21.8`. It writes the simple field back in complex form, with the change between the separator and the end. |
| `redline-reference-result-simple-locked` | As above. | As above; the lock is kept. | As above; the lock is kept. |
| `redline-reference-result-complex-control` | Only the result is tracked. | Same. | Only the result. |
| `redline-reference-result-literal-control` | Only the number is tracked. | Same. | Only the number. |
| [Calendar day](calendar-date.png) | A Tokyo host stores June 17 as June 16 at 15:00 UTC. | Stores June 17 at midnight UTC. Writer displays the same date for both. | Typing the date shows `June 17, 2034` and stores `2034-06-17T00:00:00Z`. |
| `calendar-local-timestamp` | 01:30 JST stores 16:30 UTC on the previous day. | Stores the day it was given, June 17, at midnight UTC, with the explicit display text. | A date control holds a calendar day. On save it stores the day the control shows at midnight UTC, and removes the value when the text is not a date. |
| `calendar-utc-midnight-control` | Stores June 17 at midnight UTC. | Same. | Same day. |
| [Adjacent list starts](nested-adjacent-starts.png) | The first children receive flat labels 8 and 9. | Matches Writer's 7.8 and 7.9. | 7. 7.8 7.9 8. 8.8 |
| [Implicit list parent](nested-implicit-parent.png) | Flat labels 8 and 9. | Matches Writer's 7.8 and 7.9 without a physical parent paragraph. | 7.8 7.9 |
| [Child start of one](nested-start-one-control.png) | Matches Writer. | Same five labels. | 7. 7.1 7.2 8. 8.1 |
| `nested-advanced-parent` | Flat labels 10 and 11 after the parent has counted to 9. | 9.10 and 9.11. | 7. 8. 9. 9.10 9.11 |
| `nested-continued-legal` | Flat label 4, the shape a removed Docxodus rule was written for. | 3.4. | 1. 2. 3. 3.4 |

## What changed in this revision

The reference application's readings changed three expectations and added six cases.

- `calendar-timestamp-control` is now `calendar-local-timestamp`, a reproducer. The application stores the calendar day it shows, at midnight UTC. It does not store the instant of the value's time, so a local time early on June 17 stores June 17. `calendar-utc-midnight-control` is the new control: an explicit UTC midnight was stored as the right day before the fix too.
- `nested-advanced-parent` and `nested-continued-legal` pin a deeper item after its parent has counted on. Docxodus used to render it as a flat continuation of the parent's list. The application keeps the parent's number in every shape measured (23 fixtures), including the one the rule was written for. Docxodus #1850 now removes the rule rather than narrowing it.
- The four `redline-reference-result-*` cases pin Docxodus #1844. A simple field's expected documents hold the field in complex form, because that is how both reference applications resolve it: the desktop word processor's own compare writes it that way, and LibreOffice exports a simple field in complex form.

The application also marks a moved one-word paragraph (`Scope`) as a move. So a global minimum anchor length is not its default, and the numbered-entry insertion and removal keep requesting `minimumAnchorWordCount=2` explicitly.

## Measurement

Projection: Docxodus main `3d9efb03c257f803bc635323b8320ae9799f03fd` passes 37 of the 41 non-date cases. It fails the four nested-list reproducers, and the previous list fix `8ce8c31dc638a89ab377d7d03df48b1f2ce7e283` still fails the two new ones. The list fix `e43306975776ccd091192952ea3cf921d53828a2` passes all 41. Those runs called this track's adapter directly on Windows, with the same per-case checks. The date cases' Tokyo host needs POSIX, so the earlier measurement (baseline `965c3fde`, date fix `e0b33815`) is kept in observations.json; under the new expectation both fail `calendar-local-timestamp`. The date fix `f1f04108028da7f97d0915ffd440e395def1268d` no longer depends on the host's time zone. Its public stdio host, making the same calls as this track's adapter on a UTC−6 host, stored `2034-06-17T00:00:00Z` for all three date cases, and Docxodus's own CI runs its east-of-UTC test on Linux.

Redline: every check the harness defines ran, except the LibreOffice text round trip, because LibreOffice was not available on the capture machine (CI runs it). That is markup accept and reject, SDK validity, and the declared assertions. The authored redlines score 100 on all seven cases. Main scores 0 on both simple-field reproducers (untracked prose, revision count) and 100 on both controls. It cannot run the numbered-entry insertion or removal, which request a setting it does not have. The field fix `c085b026e640b222b72a3c95c2c4d49a85ac7f10` scores 100 on all four field cases, and the reference application resolves its redlines to one live field with the right result and lock state. The numbered-entry fix `68616fbf336328cfc524932c64785fcaaa903b1b` scores 100 on all three numbered-entry cases. The reference application opens its redlines; Accept All gives the revised text and Reject All the original. With the minimum at 2 it also keeps a moved one-word heading as a move, as the reference does. The reference application opens every authored redline; Accept All gives the revised text and Reject All the original, with no revision left.

Use `python3 -m bench.projection build` and `run` for the complete projection suite. For the comparison diagnostic, build the validator and redline adapter, then run `python3 -m bench redline run` with the case IDs above. In the PNGs, the reference column shows the independently authored OOXML redline and the other redline columns show actual Docxodus output rendered by Writer.
