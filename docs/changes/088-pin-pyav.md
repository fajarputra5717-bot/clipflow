# 088 · Pin PyAV < 19 (transcription would fail on the next import) · worker/requirements.txt

**Found by Lane B.** The worker image resolved `av` 19.0.0 (faster-whisper 1.2 only requires `av`). PyAV 19
removed the `metadata_errors` keyword from `av.open()`, which `faster_whisper.audio.decode_audio()` passes,
so every transcription raised `TypeError: open() got an unexpected keyword argument 'metadata_errors'`.
Reproduced in the running worker before the fix.

**Now.** `av<19` in `worker/requirements.txt` (resolves 18.1.0); worker rebuilt.

**Verified** on the stack: `decode_audio()` on a final → OK with av 18.1.0; one short import end to end:
npDdITTUgl8 (4.7 min) → auto-detect id 0.81, 112 segments with word timings (247.7 s), AI hooks, 2 previews
in review with `subtitle_override` NULL and per-word segments (083 path intact).
