# 187 · "Found, not imported: confirm?" + worker/assets/LICENSES.md (2026-10-12, owner request)

- Campaign page → Auto-import box lists the caller's skipped videos the rules couldn't vouch for
  (`auto_import.CONFIRMABLE`: "No upload time", "Older than the watch", "Unknown length"; rule-outs such as "Under 5 min"
  or "Daily limit" are not listed) with "Import anyway".
- `POST /api/auto-import/imports/{id}/import` (owner-scoped: new `IMPORT_PATH_RE` in the `_path_owned` guard → another
  user's row = 404): skipped + confirmable → `found` with reason `auto_import.CONFIRMED`; 409 otherwise. The import
  loop then makes the job via `create_job_for` (campaign paused/ended, "Already imported" and the disk pause still
  apply; a switched-off watch does not block a confirmed row). `GET /api/auto-import` imports carry `confirmable`.
- `worker/assets/LICENSES.md`: watermark.png = campaign watermark supplied by Motion Klip to participating clippers for
  use on campaign clips; not owned by ClipFlow; not for redistribution (owner's wording; clears Lane C's license Low).
- Verified: throwaway Postgres + backend image (guard own/other, confirmable vs not, confirmed row with watch off →
  imported job). Tests: unittest ConfirmableTest; auto-import.spec confirm list. UI 210 passed.
