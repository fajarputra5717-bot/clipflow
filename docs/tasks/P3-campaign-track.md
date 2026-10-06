# P2.5 · Schedule + P3 · Campaign screen + auto-import + Track (spec, 2026-10-07)

## P2.5 · Schedule (before P3; added 2026-10-07)

Gap: P2 built Publish (mock step 7) but not Schedule (mock step 6, "Prime time, your TZ"). P2.5 builds it
**without auto-posting**: the user still posts by hand, ClipFlow plans it and reminds them. Starts after Lane C's
P2 gate PASS; P3 starts after the P2.5 gate. Same rules as below (one commit per part, change doc, staging write
checks with lane-a-* users, `user_id` scoping, island-only progress).

| # | Part | Effort | Depends on |
|---|---|---|---|
| S1 | Suggested posting times (per user, WIB) | S | — |
| S2 | "Approve & schedule" → planned `clip_posts` | M | S1 |
| S3 | Schedule view (by day, per platform) | M | S2 |
| S4 | Telegram reminder at the planned time | M | S2, 141 send-to-phone |

**S1 · Suggested times.** `POSTING_TIMES` in `USER_SETTING_KEYS` (user → app → default), JSON
`{platform: ["HH:MM", …]}` in **WIB (Asia/Jakarta)**, defaults per platform in `DEFAULT_SETTINGS` (owner-approved
2026-10-07, common Indonesian lunch/evening peaks, user-adjustable): tiktok 12:00/19:00/21:00, instagram (Reels)
11:30/19:30, youtube (Shorts) 17:00/20:00, facebook 12:00/19:00. Keys = `rule_checks.PLATFORM_LIMITS` names. Validated
in a pure helper `shared/schedule.py` (`normalize_posting_times`, `next_slots(times, platform, after, taken)` →
the next free slots, skipping ones already taken by this user on that account and slots outside the campaign's
posting window via `payouts.window_for` / `window_problems`). Settings → Posting times editor (members edit
their own). All times stored as TIMESTAMPTZ (UTC), shown in WIB.

**S2 · Approve & schedule.** Review/Editor get "Approve & schedule" next to Approve: same approve gate (409 on
blocking `rule_checks`), then a sheet with one row per campaign platform × account: suggested slot (from S1,
editable date/time in WIB), account picker. Saving creates/updates `clip_posts` rows with `status='planned'`,
`scheduled_for` (column already exists since 129), through `shared/posts.py` validation; pre-post amber checks
(132) run against the planned time (e.g. outside window → warning, stored `eligible=false` + reason). Re-plan =
PATCH `scheduled_for`; `dropped → planned` keeps working. The final render still runs as today; a post whose
render is not done by its time is flagged in S3 and in the reminder. No new status; "scheduled" = planned +
`scheduled_for` set.

**S3 · Schedule view.** Stepper step 6 goes live (flow-preview "Schedule"): `GET /api/schedule?from&to` (own
planned posts only, 404 rules as P1.5) grouped by WIB day, then per platform/account; list view default (mobile)
+ week calendar (desktop ≥ 1000 px). Each row: thumbnail, title, campaign, platform/account, time, render state,
eligibility chip; actions: Reschedule (next free slot / pick), Send to phone now (141), Mark posted (→ Publish's
existing posted flow with URL), Drop. Overdue planned posts (time passed, not posted) shown red at the top. Empty
days show the free suggested slots. Matches the mockup's visual system; no progress UI outside the island.

**S4 · Reminder.** The notifier (already per-user since 142) checks every minute for planned posts with
`scheduled_for` ≤ now + `REMINDER_LEAD_MIN` (user setting, default 15, owner-approved) and no reminder sent yet
(`clip_posts.reminded_at`, new column, set in the same transaction). It enqueues the send-to-phone package via
the existing `telegram_sends` queue (141: video ≤ 50 MB or shrunk + caption/hashtags as 2nd message) plus a
header line "⏰ Post now: <platform> @<account> · <time WIB> · <campaign>", to the user's OWN chat (no chat → no
send, row flagged in S3). Missed reminders after a restart are sent once if < 1 h late, else only flagged. The
09:00 digest (142) lists today's scheduled posts. Progress of the package in the island (activity kind telegram).
**No auto-posting** (P5).

**Gate:** Lane C P2.5 gate in docs/qa/ (cross-user 404 on schedule/plan routes, WIB/DST-free time handling,
reminder sent once, posting-window warnings); any open High blocks P3.

Source: docs/roadmap.md (P3 row + "P3 · Campaign step spec", owner 2026-10-07). Starts after Lane C's P2.5 gate
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
