# 098 · P0 cleanup: watermark height ≥ 16 %, "Fallback language", badge v2.1117 · main.py, index.html, CLAUDE.md

- **Watermark height (QA 078 #1):** `PUT /api/settings` rejects `WATERMARK_POSITION_Y` outside 16–85 % or
  non-numeric (`validate_watermark_height`); 5–15 % used to be accepted and then clamped by the worker's 16 %
  floor. Empty = unset still allowed.
- **`WHISPER_LANGUAGE` label (QA 079 #2):** Settings shows it as "Fallback language": since 079 it's only
  used when a job has no language (API callers, 084) or as the low-confidence fallback.
- **Version badge v2.1117** (QA process note: 079/081/082 had no bump) with a "What's new" list for 076–097.

**Verified:** PUT 10 / 15 / 90 / "abc" → 400, "" → 200; badge served as "Beta · v2.1117".
