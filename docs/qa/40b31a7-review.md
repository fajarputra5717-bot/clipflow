# QA review · 40b31a7 · 123 P1.5 part 3: per-user settings, global keys admin-only, worker reads the owner's
Reviewer: Lane C · 2026-10-06 · code review (live two-user test needs P1.5 on staging)
Claims to fix the HIGH from incident-2026-10-05 (member wrote WHISPER_MODEL).
- `update_settings`: any key outside `USER_SETTING_KEYS` from a non-admin → **403** "Only an admin can change global
  settings" ✓. USER_SETTING_KEYS = subtitle defaults, caption/watermark placement, ACTIVE_WATERMARK_ID, HASHTAGS (no
  secrets, no Whisper/AI/disk) ✓. ACTIVE_WATERMARK_ID must be one of the caller's own assets (`main.py:4180`) ✓.
- `get_settings`: members get only user-scope keys; global keys hidden; secrets masked ✓.
- Worker: settings resolve per job owner via a ContextVar; all 4 task types (candidate, analysis, Submagic task,
  Submagic poll) run inside `run_as_owner` (`worker.py:7465–7495`) ✓; `RuntimeSettings` caches user rows per user_id ✓.
## Verdict
HIGH (incident) **fixed in code**; stays "pending live" until qa-multiuser.spec.js passes on staging with P1.5.
Findings: none new. Not verified: live 403 for a member (no member account outside staging).
