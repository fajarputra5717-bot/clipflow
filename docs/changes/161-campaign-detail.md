# 161 · P3 part 5: campaign detail page (plain-language rules, weeks, my numbers, watermark, questions, brief) · campaign_view.py, main.py, index.html

- **Why:** P3 spec part 5 + roadmap "P3 · Campaign step spec" item 1 (owner 2026-10-07).
- **`shared/campaign_view.py` (pure, unit-tested on the real rules):** `build(rules, now)` → status + week,
  period line, payout sentences (`payouts.describe` + min views / blocks / one claim / per-creator monthly cap /
  payment methods), platforms, hashtags in order, watermark {required, name, has_asset}, posting weeks with
  state open|closed|upcoming (+ days left), content rules, manual checks, questions {open, answered (from
  `admin_answers[_YYYY_MM_DD]`, dated)}, claim form + requirement, budget lines (refills, FCFS). Money only via
  payouts; missing fields are left out.
- **Status wording:** a campaign with no end and no "budget" in `period.until` now says "No end date set"
  (was Lane B's "Open until the budget runs out", wrong for the Motionklip pilot).
- **API:** `GET /api/campaigns/{slug}` + `view`; `GET /api/campaigns/{slug}/watermark` serves the campaign's
  watermark asset to everyone who can see the campaign (assets are owned by their uploader; campaigns are shared),
  added to `MEDIA_PATH_RE` (wrapped in `mediaUrl()`).
- **UI:** cards (whole card or "Details") open the detail inside the Campaign step; "← Campaigns" / the stepper's
  Campaign go back. Two-column boxes (Payout, Your numbers + cap meter, Posting weeks with the open week
  highlighted, Budget, Claim | Platforms, Hashtags numbered in order, Watermark preview, Content rules, Checked by
  hand, Questions: answered with admin date + open ones flagged) and the verbatim brief in a disclosure. Admins
  get Pause / Resume (PUT paused, 157).

**Verified:** unit OK (new `test_campaign_view.py` 5 + status 4); UI 157 passed (2 new detail specs: sections,
open week, hashtag order, watermark src, questions, brief, admin pause PUT, member no Pause, stepper back, 404;
screenshots `campaign-detail-{desktop,mobile}`); prod read-only: admin + member get all 3 details and the
watermark file; IME W1 open, Windah "No end date set".
