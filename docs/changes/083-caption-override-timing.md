# 083 · Captions keep karaoke: override only for real edits, word-aligned re-timing (QA #1, #3) · worker.py, index.html

**Before.** Analysis seeded `subtitle_override` with the transcript, every preview wrote it back, and Apply
always PATCHed the textarea. With an override present `apply_subtitle_override()` dropped every line's
`words` (or split the clip evenly when the line count differed), so no final ever animated (QA clips #1),
and stored `subtitle_segments` could be evenly spaced instead of the burned timing (#3).

**Now.**
- Analysis stores the transcript lines in `subtitle_text`; `subtitle_override` starts NULL. `create_preview()`
  writes `subtitle_text` (transcript) + `subtitle_segments` (what was burned), never the override.
- Frontend: textarea = override || transcript; Apply sends `subtitle_override` only when the normalised text
  changed, and `""` (clear) when it's back to the transcript.
- `apply_subtitle_override()`: difflib alignment of edited words to Whisper's words. A line whose words all
  match one whole segment IS that segment (words kept, so karaoke/word animations work). Replaced words share
  the span of what they replaced, inserted words share the neighbour gap. Line start/end follow the words.
- One-off: the 16 existing overrides all equalled the transcript → cleared; their `subtitle_segments` reset
  to the real transcript segments.

**Verified** on the stack: finals of 8b974b8e (no edit) and 93ae8661 (line 3 edited: + "BANGET") re-rendered;
re-rendered; ASS has `\kf` per word on every line incl. the edited one; frames mid-line show the two-colour
karaoke split.
