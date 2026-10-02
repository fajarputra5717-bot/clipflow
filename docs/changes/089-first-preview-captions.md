# 089 · First previews had no captions after 083 (regression fix) · worker.py

**Found** while verifying 088: both previews of a fresh import had empty `subtitle_segments` /
`subtitle_text` and no burned captions.

**Cause.** `process_analysis_job()` passes the job row it claimed at the start to `create_preview()`, and that
row's `transcript_segments` is still NULL for a new job (transcription writes it to the DB later, not to the
dict). Before 083 this was masked: analysis seeded `subtitle_override` with the transcript text, and the
override path rebuilt (static, evenly spaced) lines from it. 083 stopped the seeding, so the first preview of
every new clip had no transcript at all. Re-renders (`process_candidate_task`) were fine: they read the
transcript from the DB, which is why 083's checks on re-rendered finals passed.

**Now.** Right after transcription, `job["transcript_segments"] = segments`, so the first preview uses the
same per-word transcript as every later render (karaoke from the very first preview).

**Affected:** only the 088 test job (1decf13e, 2 clips; the last real import predates 083); its previews were
re-rendered.

**Verified** on the stack: fresh import of npDdITTUgl8 (job 80b67b41) → both first previews have per-word
segments (16/16, 20/20 lines with words), `subtitle_override` NULL, `subtitle_text` = transcript, ASS with
`\kf` on every line, frame shows the karaoke sweep. The 088 test job's previews re-rendered: 21/21, 26/26.
