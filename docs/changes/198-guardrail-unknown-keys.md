# 198 · Auto-import limits: unknown keys → 400 (Lane C Low, fresh e2e 11162f8, 2026-10-13)

- `PUT /api/auto-import/watch` with `guardrails` containing a key that isn't a limit (e.g. `maxPerDay`) now answers
  400 "Unknown limit(s): …" instead of dropping it silently (`auto_import.unknown_guard_keys`). Stored rows are still
  merged leniently (`normalize_guardrails` drops unknown keys from the DB copy). The Campaign page form sends known
  keys only. Test: unittest auto_import (unknown keys).
