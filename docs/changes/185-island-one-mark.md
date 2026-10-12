# 185 · Island: one progress mark per task + "<verb> <subject>" line (2026-10-12)

- Bug (owner screenshot, Auto-import): an indeterminate task showed the lead spinner AND the empty ring. Now:
  indeterminate = the lead spinner only (ring hidden, expanded bar hidden, no %); a task with a percent = the ring
  (+ bar, %) and the lead is the video thumbnail or a static blue dot, never a spinner. Lead/icon are re-keyed when a
  task flips between the two modes.
- Compact (and expanded title) line = `islandLine()`: `islandVerb()` by activity kind (`src`) / status + the subject:
  "Checking @windahbasudara", "Rendering <clip>", "Downloading/Transcribing/Analyzing/Importing <video>",
  "Sending to phone · <clip>", "Queued · …", "Submagic · …". aria-label + live announcement use the same line.
- Tests: island.spec — indeterminate (one spinner, no ring, no %), percent (ring, no spinner, 40%), Telegram line.
  UI 208 passed.
