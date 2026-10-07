# 159 · P3 part 3: Campaign step live — one card per campaign (status, payout sentence, my totals, budget, cap meter) · index.html, main.py, payouts.describe

- **Why:** P3 spec part 3 (flow-preview step 1 "Campaign").
- **`payouts.describe(model)`** (Lane A section at the end of shared/payouts.py): the ONE plain-language payout
  sentence: IME "Rp 200.000 per post at 40.000 views, max 2 per platform account/month", Fandra "Rp 12.000 per full
  3.000 views, max Rp 1.992.000", CPM "$1.50 (~Rp 24.750) per 1.000 views, max $300.00", else "Payout not set yet".
- **API (`_campaign_out`):** + `payout_text`, `budget_text` (rules budget: "Rp 20.000.000/month (4 refills of
  Rp 5.000.000)"), `cap_meter` (when rules state `limits.max_payout_per_creator_per_month`: the caller's claimed +
  paid this WIB month vs that cap, "Your month: Rp X of Rp 2.400.000 cap"), `mine` {posted, claimed, paid, planned,
  paid_fmt, expected_fmt} from the caller's own clip_posts (`_campaign_stats`, one grouped query), `created_by_me`
  (replaces 157's `mine` flag).
- **Budget meter, honestly:** ClipFlow can't see other clippers' use of a campaign budget, so the meter is the
  user's own month against the per-creator cap; the total budget is text.
- **UI:** stepper step 1 goes live (`data-nav="campaign"`, `#campaignSection` first in `TAB_SECTIONS`, title
  "Campaign"): card grid (3/2/1 columns), status badge (Active green, Ending soon amber, Paused grey, Ended faded,
  sorted last), detail line (week + days left), payout sentence, platforms, my posted/claimed/paid/planned, budget +
  meter. No "New campaign" button yet (part 4). Cards open the detail page in part 5.

**Verified:** UI 153 passed (new `campaigns.spec.js`: cards, order, badges, meter, paused disabled in Analyze;
shell spec: Campaign no longer "Coming in P3"; screenshots `campaign-cards-{desktop,mobile}`); unit OK; prod
read-only: both users get 3 cards, IME budget + cap meter "Rp 0 of Rp 2.400.000", Fandra/IME payout sentences as above.
