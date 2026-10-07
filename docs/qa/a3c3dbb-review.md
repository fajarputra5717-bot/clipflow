# a3c3dbb fix(posts): PATCH scheduled_for change resets the reminder only on a real change — QA 2026-10-07

Correct: compares the parsed new time with the parsed stored one; an unchanged time keeps reminded_at/status
(no duplicate reminder). The Lane C Low it cites was a QA error (see 415b1ce-review.md correction); the change is still fine.
