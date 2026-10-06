# P4 task 2 — Editor timeline: waveform + word chips, click to seek, playhead (lane B)

- `shared/timeline.py`: word list from `subtitle_segments` (clip-relative = the preview's own timeline),
  pauses ≥ 0.3 s, waveform peaks (50/s, max |sample| per 20 ms, dB-scaled −48…0 dBFS → 0…1). Cached as
  `previews/<cid>.timeline.json` (candidate id in the name: orphan-sweep rule), invalidated by a newer
  preview (mtime) or a version bump.
- Worker: `render_steps.write_timeline()` right after the preview's loudness pass (one `# lane-b hook`);
  never fatal. Only the worker has ffmpeg.
- API: `GET /api/jobs/{jid}/candidates/{cid}/editor/timeline` (owner-scoped like the rest): the cache, or
  `words_only()` (`peaks: null`) for previews rendered before this change.
- UI (editor page): timeline under the player: ruler, canvas waveform, one chip per word (100 px/s,
  horizontal scroll), red playhead (rAF while playing, follows into view), current word highlighted;
  click a chip or the waveform to seek; reloads after Render preview. Player no longer sticky (the
  compact stepper, 121, is).
- Verified on staging: before render 69 chips + no waveform; after Render preview cached (1,752 peaks,
  12 KB, ~35 s render); live UI at 1280/390: click word 20 → video 9.96 s + chip highlighted, play → playhead
  follows, no errors, no overflow. Tests: `tests/test_timeline.py` (6), 2 timeline UI specs (× 2
  viewports); UI suite on staging 54 passed; unit 69 OK.
