# A filled date control's text

Docxodus #1851. With no display text, a desktop word processor (build 16.0.20326) shows a picked date in the
control's own date format and language, and uses US English when the control names no language. Docxodus
showed the ISO day, 2034-06-17, for every control.

| Case | Kind | Control | Desktop word processor | Docxodus main `b4eeb544` | Docxodus `265cbef9` |
| --- | --- | --- | --- | --- | --- |
| `calendar-date` | reproducer | `MMMM d, yyyy`, no language | June 17, 2034 | 2034-06-17 | June 17, 2034 |
| `calendar-display-german` | reproducer | `dddd, d. MMMM yyyy`, `de-DE` | Samstag, 17. Juni 2034 | 2034-06-17 | Samstag, 17. Juni 2034 |
| `calendar-utc-midnight-control` | control | explicit display text | — | passes | passes |
| `calendar-local-timestamp` | reproducer for #1842 | explicit display text | — | passes | passes |

The control now passes its own display text, so it checks the stored day alone, as it did before this
revision. Every case also checks the stored `w:fullDate`, which is `2034-06-17T00:00:00Z` on both builds and in the
reference application.

Docxodus was measured through its public stdio host, making the same calls as this track's adapter, on a
Windows host at UTC−6. Since Docxodus #1848, a date fill no longer depends on the host's time zone. The
reference readings are in [evidence.json](evidence.json).
