# P3 · Campaign screen + auto-import + Track (spec, 2026-10-07)

Source: docs/roadmap.md (P3 row + "P3 · Campaign step spec", owner 2026-10-07). Starts after Lane C's P2 gate
PASS and the lane-b production merge (Review page + editor; see `docs/tasks/lane-b-merge-plan.md`). One commit per
part, `docs/changes/` entry each, verified on the running stack (write checks on staging with lane-a-* users only),
report after each part. Money: IDR first, every amount from `shared/payouts.py` (never computed in index.html).
Every new table carries `user_id` (P1.5); campaigns are a shared catalogue with `created_by` + `visibility`.

Effort: S ≈ ½ day, M ≈ 1 day, L ≈ 2 days (incl. tests, docs, deploy, verification).

| # | Part | Effort | Depends on |
|---|---|---|---|
| 1 | Campaigns in the DB | M | — |
| 2 | Campaign status engine | S | 1 |
| 3 | Campaign step: cards | M | 1, 2 |
| 4 | New campaign: brief → rules (confirm before saving) | L | 1, Lane B `brief_parser` |
| 5 | Campaign detail page | M | 1, 2 |
| 6 | Campaign-driven clip/post labels + Expired group | M | 2, lane-b merge (Review/Editor pages) |
| 7 | Auto-import (source_watch) | L | 1, Lane B `source_watch` (not built yet) |
| 8 | Track dashboard (IDR) | M | P2 `clip_posts`, `payouts.py` |

## 1 · Campaigns in the DB (M)
- `campaigns` table: slug (PK), name, rules JSONB (the rules.json schema), brief_text (verbatim), created_by
  (user), visibility `shared|private` (private = creator + admins), paused BOOL, created/updated_at.
- First run imports `docs/campaigns/*.rules.json` (+ `.md` brief via `brief_parser.extract_brief`) as shared,
  created_by = bootstrap admin. `shared/campaigns.get/load_all` read the DB (files stay as seed/backup).
- Admin edits; members read shared + their own private ones (404 otherwise). Existing `jobs.campaign` slugs keep
  working.

## 2 · Campaign status engine (S)
- `shared/campaign_status.py`: `status(rules, now)` → Active / Ending soon (≤ 3 days to period end or last week's
  end) / Ended / Paused (flag); `current_week(rules, now)` → id + days left (IME weeks via `payouts.window_for`).
- Unit tests on the real rules (IME W1–W4 incl. 29–31 Oct = Ended for posting; Fandra open-ended = Active).

## 3 · Campaign step: cards (M)
- Stepper step 1 goes live (flow-preview "Campaign"): one card per visible campaign: status badge, payout summary
  line in IDR (`payouts` plain-language formatter, e.g. "Rp 200.000 per post at 40.000 views, max 2 per platform
  account/month", "Rp 12.000 per full 3.000 views, max Rp 1.992.000"), platforms, due/week + days left, my
  posted/claimed counts, budget meter when the rules state a budget.
- Plain-language payout text lives in `shared/payouts.py` (`describe(model)`), not the frontend.

## 4 · New campaign: brief → rules (L)
- "New campaign": paste brief → `brief_parser.parse_brief(text, today, ai=router_ai())` (patterns first, AI only
  for gaps) → form with every rule pre-filled; `unsure` / `ai_derived` fields highlighted and must be confirmed;
  admin saves (members: admin-only for shared; private campaigns per owner decision later). Brief kept verbatim.
- Progress of the AI fallback in the island (`/api/activity`), never a spinner.

## 5 · Campaign detail page (M)
- Brief verbatim; rules in plain language (payout in IDR, caps, min views); platforms; hashtags in order;
  watermark preview (asset); posting windows/weeks (open week highlighted); content rules; open questions with
  admin answers; claim form link; budget/refill schedule; my totals (posted, claimed, paid; Rp from paid_rp /
  expected_rp, formatted by payouts).

## 6 · Campaign-driven labels (M)
- Review, Editor and Publish show "Week closed", "Campaign ended", "Not eligible: <reason>" badges from part 2 +
  `posts.eligible`; claim advice "Missed" + reason (exists since 133).
- Ended campaigns' clips leave the active queue for a collapsed "Expired" group (Review + Publish). Nothing is
  deleted; the digest (142) skips expired clips.

## 7 · Auto-import via source_watch (L)
- Per campaign, source channels (rules `sources`) with watch switches (flow-preview step 2); a worker queue polls
  each watched channel (yt-dlp, metadata only) every N minutes, imports new videos as jobs owned by the user who
  switched it on, with the campaign defaults (layout, language, clips); "recent imports" list; checks in the
  island. Dedupe by URL per user; disk reserve (R-14) respected.
- Blocked until Lane B ships `shared/source_watch.py` (not on lane-b yet).

## 8 · Track dashboard (M)
- Stepper step 8 (flow-preview "Track"): tiles (views, earnings in Rp, claimed vs paid, clips at cap), per-campaign
  and per-platform breakdown, top clips by views with expected vs paid; all amounts via `payouts` (IDR, non-IDR
  shown "$12.40 (~Rp 204.600)"). Data = this user's `clip_posts` + `clip_post_views` (P5 fills views automatically).

## Gate
Lane C P3 gate in docs/qa/; any open High blocks P4.
