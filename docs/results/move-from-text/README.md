# Move-source text previews

These previews show four benchmark cases generated with a local Docxodus
build based on `12c76034` plus the in-progress #1420 change. LibreOffice 25.8.7.3 exported each
candidate redline to PDF; `pdftoppm` rasterized page one. The labels identify each case and
renderer. These images are LibreOffice review evidence, not Word validation.

| Case | Candidate DOCX SHA-256 | Preview |
| --- | --- | --- |
| Moved paragraph | `de267d4a1b8cdd62be239470eb71ac1d5685c1d9c9d45bb70a8d9ff7093280c4` | [Moved paragraph](move.png) |
| Ordinary replacement control | `2b8ca298687e393500375cca95aed453847165db5a79412487813c57abea1de7` | [Replacement control](control.png) |
| Consolidated move | `316e983d5e6db76d296732990ac9e947bff49c2bbb661d0502e17e2311f2f3b2` | [Consolidated move](consolidate.png) |
| Consolidated replacement control | `50b12bdb2a4a1b0c20bb99c522933f258949cfec45e0bedcc90b820a481cf6d4` | [Consolidated replacement](consolidate-control.png) |

The benchmark's independent resolver reproduces both expected views for each candidate; the
revision-text assertion checks move-source and ordinary deletion spelling. The authored calibration
measured 100 for each case, with all eight LibreOffice accept/reject checks applicable. The Open XML
SDK 3.5.1 reported no findings on the authored cases or the four candidate outputs. This was a
focused four-case run, not a complete suite score. The consolidated benchmark cases contain two
reviewers; the separate Word Online check below used one reviewer.

Word Online, opened through authenticated Playwright on October 29, 2026, displayed both the
[current-main output](word-baseline.png) and [proposed output](word-fixed.png) without an error.
The baseline output SHA-256 is `4dece9fd81fae89c03dd5f628a74f3ff0f7c244af631198fc0f25a20b45b1479`;
it contains `w:delText` under `w:moveFrom`. The proposed output uses `w:t` there. These observations
do not reproduce the issue reporter's desktop Word opening failure; the web and desktop products
may differ. Word Online did not report a build number.

The same input pair was consolidated with one reviewer. Word Online also opened both the
baseline (`d910d694f1958c97619eca0bf5a0e8c9feed8aad6f7d5b36c531c3366d714baa`) and proposed
(`bcd77724452329228ba309f5f3c83eb1a5520d30da0943430662ef18502998c8`) consolidated outputs and
displayed the move after a transient network retry.
