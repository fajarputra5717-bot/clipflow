# 081 · Campaign flow v1 (rules files → job campaign, watermark preset, hashtags, prompt context, rule skips) · main.py, worker.py, index.html, shared/campaigns.py, docker-compose.yml

**Before.** Campaign rules lived only as docs (`docs/campaigns/*.rules.json`, 078); nothing read them.

**Now.**
- `shared/campaigns.py` loads `docs/campaigns/<slug>.rules.json` (+ `<slug>.md` brief), bind-mounted
  read-only at `/app/campaigns` in backend and worker, re-read on mtime change (no rebuild to edit rules).
  A brief whose `.md` lacks `--- BRIEF START ---` = `brief_pending` (Motionklip Windah).
- `GET /api/campaigns` (summary: name, sources, platforms, brief_pending). `jobs.campaign` (slug, NULL = none),
  validated on `POST /api/jobs` (unknown → 400).
- Watermark preset snapshotted at creation like R-05/R-17: `jobs.watermark_asset_id` (asset by id; resolved
  per render by `resolve_watermark_path(asset_id)`), width, opacity, centre y; the 078 16 % floor still applies.
- AI description ends with the campaign hashtags in exact order (`with_campaign_hashtags()`).
- Hook prompt (campaign jobs only, non-campaign prompt byte-identical): title language, title examples
  ("don't copy"), clip-checkable content rules; schema adds required `rule_flags`. `drop_rule_breakers()` skips
  flagged clips and logs `Campaign <slug>: skipped clip … breaks <rule>`. Posting-behaviour rules
  (`POSTING_RULES`) are left for v2a pre-post checks.
- UI: Import "Campaign" dropdown + source hint; campaign tag on job cards and Publish rows; Publish filter
  by campaign (All / each used / No campaign).

**Verified** on the stack: one job per campaign (Fandra, IME, Windah), each rendered a final with the
Motion Klip watermark at ~25 % (frames checked); descriptions end with the exact hashtag lists; IME logged
two skipped clips (`no_negative_narrative_about_others`); `/api/campaigns` shows Windah as brief pending.

**Open (resolved in 093: order only, at the end).** The rules files say hashtags go FIRST in the caption ("nothing before them"); v1 appends them at
the END of the AI description as specified. The v2a "copy caption" step must put them first.
