# 208 · Island "+N" opens a live list of every active task (owner bug, 2026-10-14)

Bug: "Importing SEHARUSNYA … +1" and no way to see the +1. Cause (desktop): hover-expand listened on the whole `#island`,
which contains "+N"; the expanded shape merges "+N" into the island, so reaching for it expanded the island and the
circle vanished under the pointer (reproduced: after hovering "+N", visible = false; the click opened nothing). The
expanded island shows only the lead task, so the others could not be seen at all. On phones the tap worked, but the
list's rows said "YouTube Shorts" (the platform) instead of the job, in 9–10 px text.
Fix:
- Hover-expand starts on `#islandMain` only; "+N" also stays beside the hover-expanded island on desktop (> 600 px),
  and hovering it cancels a pending collapse. Opening the list collapses a hover/pinned expansion and blocks
  hover-expand while open (it covered the first row).
- "+N": aria-haspopup / aria-controls="jobOverlay" / aria-expanded (synced in `renderJobOverlay`); Enter/Space native;
  opened by keyboard → focus moves to the first row; Esc closes and returns focus to "+N" (or the pill); outside click
  closes; the list closes itself when the last task finishes; closed = hidden + inert (202).
- The pill: 2+ tasks → opens/closes the list; exactly 1 → `openRunningTask()` opens it (job → Analyze monitor, clip task →
  `#review/<job>`, auto-import check → `#import`); tasks with nowhere to go (Telegram, views) keep the expand toggle.
- Rows are `<button>`s: thumbnail (or the indeterminate spinner) · name (`islandTitle`) · stage (`islandVerb`:
  Downloading / Analyzing / Rendering…) · progress ring (hidden for indeterminate) · "Open ›"; aria-label
  "<name>: <stage>, N%. Open". Row clicks go through the same `openRunningTask()`. Text 12–13 px, solid card.
- Live: rows stay keyed and patched on every poll (added/removed while open).
Spec: island-list.spec.js (2 and 3 jobs at 1440×900 and 390×844: real pointer hover → +N still visible → click, tap,
names/stages/aria-label, outside click; keyboard Enter/Esc/Space with focus; pill opens the list; live add/remove +
auto-close; one job: no +N and the pill opens it). UI 252 passed.
