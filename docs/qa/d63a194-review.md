# QA review · d63a194 · 081 campaign flow v1

Reviewer: Lane C · 2026-10-02 · reviewed against main @ c954a82

Invariants checked: ensure_schema (`jobs.campaign`, `jobs.watermark_asset_id`, `IF NOT EXISTS`, OK) ·
non-campaign hook prompt byte-identical (`campaign_block`/`flags_field` empty, title rule unchanged,
OK) · non-campaign description prompt text unchanged (OK) · `resolve_watermark_path(asset_id)` threaded
through create_preview (`worker.py:4595`), render_final_candidate (`:4861`), Submagic overlay (`:4038`)
and passed as `watermark_path=` to both `make_ass` and `render_vertical` at every call site, so the
argless fallbacks at `:3690`/`:4231` never fire for jobs (OK; clean plate renders `watermark=False`) ·
`claim_candidate_task` + Submagic SELECTs carry the new columns (OK) · new GET route isn't a file route
(no `MEDIA_PATH_RE` needed); frontend uses `api("/api/campaigns")` (OK) · AI errors still propagate
(rule-flag drop only filters parsed hooks).

## Findings (most severe first)

1. ~~High · hashtags at the end~~ **WITHDRAWN 2026-10-02 (owner):** the briefs require exact order only;
   end of caption is intended. The rules files' `required_prefix` key and the "first in the caption;
   nothing before them" text are a **wording bug in `docs/campaigns/*.rules.json`** (Lane A to reword).
   QA checks order only. Live: order correct on all 3 finals.
2. **Medium · a "required" campaign watermark silently falls back.** If the preset asset isn't in the
   library (deleted, or matched by name and missing), `campaign_watermark_snapshot()` stores NULL and
   the job renders with the *active* watermark; the worker resolver does the same for a vanished
   asset. Only a print/log line. For `"required": true`, this should block the job or show a warning
   in the UI.
3. **Medium · rule-flag drop relies on the model.** Gemini receives no schema (R-20), so the
   `rule_flags` enum is only enforced for Claude. Unknown ids are ignored by `drop_rule_breakers`
   (good), but a model that omits `rule_flags` keeps every clip. No QA-visible record of
   which clips were dropped beyond a log line.
4. **Low · rules file parse failure is silent.** A JSON error in `<slug>.rules.json` drops the
   campaign from `load_all()`. Existing jobs with that slug then get no hashtags and no prompt
   context (`job_campaign_of` → None), with no log line.
5. **Low · `new_hook` / `fix_subtitle_ai` have no campaign context** (titles from "new hook" ignore
   the campaign's title language/examples and rule flags).
6. **Process** · no badge bump (still v2.1116) for a user-visible feature.

## Not verified
- A fresh campaign job end-to-end (analysis with campaign context + rule drops). The 3 existing
  campaign jobs were analysed before 081; QA saw only their descriptions/watermark.
- `docker-compose.yml` mount: ro bind of `docs/campaigns` on backend+worker (read only from the diff).
