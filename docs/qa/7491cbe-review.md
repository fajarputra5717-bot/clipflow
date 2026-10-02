# QA review · 7491cbe · 098 P0 cleanup: watermark height 16–85 %, "Fallback language" label, badge v2.1117

Reviewer: Lane C · 2026-10-02

`validate_watermark_height()` rejects < 16 or > 85 on settings PUT (no silent clamp); Settings label for
`WHISPER_LANGUAGE` = "Fallback language"; badge **v2.1117** (QA process item closed).

## Findings
- **Low · the job-creation clamp still says 5–95** (`percent_setting("WATERMARK_POSITION_Y", 25.0, 5, 95)` in
  create_job): unreachable now through Settings, but an env value of e.g. 10 would still be snapshotted and then
  clamped by the worker. Cosmetic.
- **Not in this commit (P0 fold-ins from 090, owner 2026-10-02):** `/api/activity` errors still swallowed
  (`index.html:2641` `.catch(()=>null)`), job filter still a resting-state deny-list (`JOB_RESTING`, main.py:890),
  no indeterminate Submagic state. See gate-P0.md.
