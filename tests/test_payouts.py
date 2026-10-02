"""Unit tests for shared/payouts.py. Run: python -m unittest tests.test_payouts"""

import json
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from shared import payouts as p

WIB = p.WIB
CAMPAIGNS = Path(__file__).resolve().parent.parent / "docs" / "campaigns"


def wib(y, mo, d, h=12, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=WIB)


IME = p.FixedThreshold(
    amount=200_000, min_views=40_000, max_eligible_per_account_month=2,
    windows=(p.Window("W1", date(2026, 10, 1), date(2026, 10, 7)),
             p.Window("W2", date(2026, 10, 8), date(2026, 10, 14)),
             p.Window("W3", date(2026, 10, 15), date(2026, 10, 21)),
             p.Window("W4", date(2026, 10, 22), date(2026, 10, 28))))
FANDRA = p.PerBlock(per_block=12_000, block_views=3_000, min_views=3_000, max_counted_views=500_000)


class Money(unittest.TestCase):
    def test_format(self):
        self.assertEqual(p.format_idr(1_992_000), "Rp 1.992.000")
        self.assertEqual(p.format_idr(0), "Rp 0")
        self.assertEqual(p.format_idr(None), "Rp ?")


class FixedThreshold(unittest.TestCase):
    def test_payout_flat(self):
        self.assertEqual(p.payout_for(IME, 39_999), 0)
        self.assertEqual(p.payout_for(IME, 40_000), 200_000)
        self.assertEqual(p.payout_for(IME, 2_000_000), 200_000)
        self.assertEqual(p.max_payout(IME), 200_000)

    def test_windows_are_wib_days(self):
        # 23:30 WIB on Oct 7 is W1; 00:30 WIB Oct 8 (= 17:30 UTC Oct 7) is W2
        self.assertEqual(p.window_for(IME, wib(2026, 10, 7, 23, 30)).id, "W1")
        utc_late = datetime.fromisoformat("2026-10-07T17:30:00+00:00")
        self.assertEqual(p.window_for(IME, utc_late).id, "W2")
        self.assertIsNone(p.window_for(IME, wib(2026, 10, 29)))
        self.assertEqual(IME.windows[0].closes_at(), wib(2026, 10, 8, 0, 0))

    def test_claim_now_when_reached(self):
        a = p.claim_advice(IME, views=41_000, uploaded_at=wib(2026, 10, 2), now=wib(2026, 10, 5))
        self.assertEqual((a.action, a.reason, a.payout_now), ("claim_now", "threshold_reached", 200_000))
        self.assertEqual(a.deadline, wib(2026, 10, 8, 0, 0))
        self.assertIn("first come", a.message)

    def test_wait_shows_need_and_time_left(self):
        a = p.claim_advice(IME, views=25_000, uploaded_at=wib(2026, 10, 2), now=wib(2026, 10, 6, 12))
        self.assertEqual((a.action, a.reason, a.views_needed), ("wait", "below_target", 15_000))
        self.assertIn("1 d 12 h left in week W1", a.message)

    def test_missed_cases(self):
        up = wib(2026, 10, 2)
        late = wib(2026, 10, 8, 0, 1)
        self.assertEqual(p.claim_advice(IME, views=50_000, uploaded_at=up, now=late).reason, "window_closed")
        self.assertEqual(p.claim_advice(IME, views=10_000, uploaded_at=up, now=late).reason,
                         "window_closed_below_target")
        self.assertEqual(p.claim_advice(IME, views=50_000, uploaded_at=wib(2026, 10, 30), now=wib(2026, 10, 30)).reason,
                         "outside_windows")
        self.assertEqual(p.claim_advice(IME, views=50_000, uploaded_at=up, now=wib(2026, 10, 3),
                                        account_claims_this_month=2).reason, "account_limit_reached")
        self.assertEqual(p.claim_advice(IME, views=50_000, uploaded_at=up, now=wib(2026, 10, 3),
                                        budget_exhausted=True).reason, "budget_exhausted")

    def test_second_slot_still_open(self):
        a = p.claim_advice(IME, views=40_000, uploaded_at=wib(2026, 10, 9), now=wib(2026, 10, 9),
                           account_claims_this_month=1)
        self.assertEqual(a.action, "claim_now")

    def test_claimed_and_month_key(self):
        a = p.claim_advice(IME, views=40_000, uploaded_at=wib(2026, 10, 9), now=wib(2026, 10, 9), claimed=True)
        self.assertEqual(a.action, "claimed")
        self.assertEqual(p.month_key(datetime.fromisoformat("2026-09-30T18:00:00+00:00")), "2026-10")

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            p.claim_advice(IME, views=1, uploaded_at=datetime(2026, 10, 2), now=wib(2026, 10, 2))


class PerBlock(unittest.TestCase):
    def test_full_blocks_only(self):
        cases = {2_999: 0, 3_000: 12_000, 5_999: 12_000, 6_000: 24_000, 499_999: 1_992_000,
                 500_000: 1_992_000, 900_000: 1_992_000}
        for views, want in cases.items():
            self.assertEqual(p.payout_for(FANDRA, views), want, views)
        self.assertEqual(p.max_payout(FANDRA), 1_992_000)

    def test_next_block(self):
        self.assertEqual(p.views_to_next_block(FANDRA, 1_000), 2_000)
        self.assertEqual(p.views_to_next_block(FANDRA, 4_500), 1_500)
        self.assertIsNone(p.views_to_next_block(FANDRA, 498_000))

    def test_advice(self):
        up, now = wib(2026, 10, 1), wib(2026, 10, 3)
        adv = lambda **kw: p.claim_advice(FANDRA, uploaded_at=kw.pop("up", up), now=kw.pop("now", now), **kw)
        self.assertEqual(adv(views=2_000).reason, "below_minimum")
        self.assertEqual(adv(views=498_500).reason, "at_cap")
        a = adv(views=60_000, views_24h_ago=58_500)
        self.assertEqual((a.action, a.reason, a.payout_now), ("claim_now", "growth_stalled", 240_000))
        a = adv(views=60_000, views_24h_ago=30_000)
        self.assertEqual((a.action, a.reason), ("wait", "still_growing"))
        self.assertIn("Rp 360.000 tomorrow", a.message)  # 90k at this pace → 30 blocks
        self.assertEqual(adv(views=60_000).reason, "early")
        self.assertEqual(adv(views=60_000, now=wib(2026, 10, 9)).reason, "settled")
        self.assertEqual(adv(views=60_000, campaign_end=wib(2026, 10, 3, 20)).reason, "ending_soon")
        self.assertEqual(adv(views=60_000, campaign_end=wib(2026, 10, 2)).action, "missed")
        self.assertEqual(adv(views=60_000, budget_exhausted=True).reason, "budget_exhausted")


class Currency(unittest.TestCase):
    def test_format_and_convert(self):
        from decimal import Decimal as D
        self.assertEqual(p.format_with_idr(D("12.40"), "USD"), "$12.40 (~Rp 204.600)")
        self.assertEqual(p.format_with_idr(200_000, "IDR"), "Rp 200.000")
        self.assertEqual(p.format_with_idr(D("12.40"), "USD", usd_idr=16_000), "$12.40 (~Rp 198.400)")
        self.assertEqual(p.format_money(D("1234.5"), "EUR"), "€1,234.50")
        self.assertEqual(p.format_with_idr(D("3"), "CHF"), "3.00 CHF (~Rp ?)")
        self.assertEqual(p.to_idr(D("3"), "EUR", rates={"EUR": 18_000}), 54_000)
        self.assertEqual(p.total_idr([(200_000, "IDR"), (D("12.40"), "USD"), (D("1"), "CHF")]),
                         (404_600, ["CHF"]))

    def test_foreign_amounts_are_never_integers(self):
        from decimal import Decimal as D
        self.assertEqual(p.as_money(12.4, "USD"), D("12.4"))
        self.assertIsInstance(p.as_money(12.4, "USD"), D)
        self.assertEqual(p.as_money("12000", "IDR"), 12_000)
        m = p.FixedThreshold(amount=p.as_money("7.5", "USD"), min_views=1000, currency="USD")
        self.assertEqual(str(p.payout_for(m, 1000)), "7.5")

    def test_cpm(self):
        from decimal import Decimal as D
        m = p.Cpm(rate_per_1000=D("1.5"), currency="USD", min_views=10_000, max_payout=D("300"))
        self.assertEqual(p.payout_for(m, 9_999), 0)
        self.assertEqual(str(p.payout_for(m, 10_001)), "15.00")   # cents kept, rounded down
        self.assertEqual(str(p.payout_for(m, 123_456)), "185.18")
        self.assertEqual(p.payout_for(m, 900_000), D("300"))
        self.assertEqual(p.max_payout(m), D("300"))
        idr = p.Cpm(rate_per_1000=5_000, currency="IDR")
        self.assertEqual(p.payout_for(idr, 1_499), 7_495)

    def test_cpm_advice_shows_both_currencies(self):
        from decimal import Decimal as D
        m = p.Cpm(rate_per_1000=D("1.5"), currency="USD", min_views=10_000, max_payout=D("300"))
        up, now = wib(2026, 10, 1), wib(2026, 10, 3)
        a = p.claim_advice(m, views=50_000, views_24h_ago=49_800, uploaded_at=up, now=now)
        self.assertEqual((a.action, a.reason, a.currency), ("claim_now", "growth_stalled", "USD"))
        self.assertEqual(a.payout_now, D("75.00"))
        self.assertEqual(a.payout_now_idr, 1_237_500)
        self.assertIn("$75.00 (~Rp 1.237.500)", a.message)
        self.assertEqual(p.claim_advice(m, views=250_000, uploaded_at=up, now=now).reason, "at_cap")
        self.assertEqual(p.claim_advice(m, views=4_000, uploaded_at=up, now=now).views_needed, 6_000)
        b = p.claim_advice(m, views=50_000, views_24h_ago=20_000, uploaded_at=up, now=now, usd_idr=16_000)
        self.assertEqual((b.action, b.payout_now_idr), ("wait", 1_200_000))

    def test_model_from_rules_currencies(self):
        r = {"payout": {"model": "cpm", "currency": "USD", "rate_per_1000": 1.5, "max_payout_per_video": 300},
             "min_views_to_qualify": 10_000}
        m = p.model_from_rules(r)
        self.assertEqual((type(m).__name__, m.min_views, str(m.rate_per_1000)), ("Cpm", 10_000, "1.5"))
        self.assertIsInstance(p.model_from_rules({"payout": {"model": "cpm", "currency": "UNSTATED", "rate": 2}}), p.Unknown)


class Unknown(unittest.TestCase):
    def test_unknown(self):
        m = p.Unknown("TBD")
        self.assertIsNone(p.payout_for(m, 1_000_000))
        a = p.claim_advice(m, views=1, uploaded_at=wib(2026, 10, 1), now=wib(2026, 10, 1))
        self.assertEqual((a.action, a.payout_now), ("unknown", None))


class FromRules(unittest.TestCase):
    def load(self, slug):
        return json.loads((CAMPAIGNS / f"{slug}.rules.json").read_text(encoding="utf-8"))

    def test_ime(self):
        m = p.model_from_rules(self.load("ime-roleplay"))
        self.assertIsInstance(m, p.FixedThreshold)
        self.assertEqual((m.amount, m.min_views, m.max_eligible_per_account_month), (200_000, 40_000, 2))
        self.assertEqual([w.id for w in m.windows], ["W1", "W2", "W3", "W4"])
        self.assertEqual(m.windows[3].end, date(2026, 10, 28))

    def test_fandra_uses_stated_blocks_not_per_view(self):
        m = p.model_from_rules(self.load("fandra-octo"))
        self.assertEqual(m, FANDRA)
        self.assertEqual(p.max_payout(m), 1_992_000)  # rules.json says 2,000,000: per-view math

    def test_motionklip_unknown(self):
        self.assertIsInstance(p.model_from_rules(self.load("motionklip-windah")), p.Unknown)
        self.assertIsInstance(p.model_from_rules(None), p.Unknown)


if __name__ == "__main__":
    unittest.main()
