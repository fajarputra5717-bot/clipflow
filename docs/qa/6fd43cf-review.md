# QA review · 6fd43cf · 089 first-preview captions (regression from 083)

Reviewer: Lane C · 2026-10-02

Fix: `_process_analysis_job` puts the fresh `segments` into `job["transcript_segments"]` before the first
`create_preview()` (the claimed row predates transcription, so the dict held NULL; 083 stopped hiding this by
seeding `subtitle_override`). Reanalyze path already carries the stored transcript.

## Re-check: FIXED (fresh import)
QA e2e job f20ba7e7 (new import): both first previews have 14/18 lines with word timings and burned karaoke
captions (see fd96c63-review). This is the path the 083 re-check missed: QA tested re-renders only.

## Findings
- **Process (QA):** from now on every caption/render check includes a fresh import → first preview → final.
- No code findings.
