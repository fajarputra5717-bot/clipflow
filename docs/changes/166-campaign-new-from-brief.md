# 166 · P3 part 4 — New campaign: brief → rules, confirm before saving (2026-10-09)

- `POST /api/campaigns/parse-brief` (admin): `brief_parser.parse_brief(text, today=WIB, ai=router_ai())` — patterns
  first, AI (utility provider, task "brief") only for gaps. Returns rules without parse metadata + `unsure`,
  `ai_derived`, a free slug, and the plain-language preview (`campaign_view.build` + `payouts.describe`). Saves nothing.
- `POST /api/campaigns/preview` (admin): the same preview for edited rules (400 on unreadable shapes).
- `POST /api/campaigns` (admin, 201): 409 unless every `unsure` field is in `confirmed`; slug `SLUG_RE`, unique (409);
  ≥ 1 known platform; brief stored verbatim; `created_by` = the admin; visibility shared|private.
- UI: "New campaign" (admins) on the Campaign step → paste → form (name, short name, who sees it, platform chips,
  hashtags in order, All rules JSON) with unsure fields highlighted + a Confirm tick each; Save disabled until all are
  ticked. The parse call shows in the island (client task, indeterminate) — no spinner.
- Deviation: the island entry is client-registered (like the other synchronous AI calls), not an `/api/activity` row.
- Checks: UI 171 passed (new campaign-new.spec); live backend read-only: parse (AI fallback filled 3 fields, all
  unsure), preview, member 403. No staging write check of the save yet (staging runs lane-b).
