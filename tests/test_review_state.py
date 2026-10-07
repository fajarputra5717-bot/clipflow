"""Review header status + earn state (P4 task 6 filters). Run: python -m unittest tests.test_review_state"""

import json
import unittest
from datetime import datetime
from pathlib import Path

from shared import payouts
from shared.review_state import campaign_status, earn_state

CAMP = Path(__file__).resolve().parent.parent / "docs" / "campaigns"
IME = json.loads((CAMP / "ime-roleplay.rules.json").read_text(encoding="utf-8"))
FANDRA = json.loads((CAMP / "fandra-octo.rules.json").read_text(encoding="utf-8"))
wib = lambda *a: datetime(*a, tzinfo=payouts.WIB)


class Status(unittest.TestCase):
    def test_ime_weeks(self):
        self.assertEqual(campaign_status(IME, wib(2026, 10, 9, 12))["text"], "Week 2 · 6 days left")
        self.assertEqual(campaign_status(IME, wib(2026, 10, 7, 23))["text"], "Week 1 · 1 day left")
        self.assertEqual(campaign_status(IME, wib(2026, 10, 30, 10)), {"text": "All weeks closed", "ended": True})

    def test_open_ended_and_ended_period(self):
        self.assertEqual(campaign_status(FANDRA, wib(2026, 10, 9))["text"], "Open until the budget runs out")
        ended = {**FANDRA, "period": {"start": "2026-09-30", "end": "2026-10-05"}}
        self.assertEqual(campaign_status(ended, wib(2026, 10, 9)), {"text": "Ended", "ended": True})
        self.assertEqual(campaign_status({**FANDRA, "period": {"start": "2026-09-30", "end": "2026-10-20"}}, wib(2026, 10, 9))["text"],
                         "12 days left")


class Earn(unittest.TestCase):
    def test_week_closed_for_posts_in_closed_weeks(self):
        m = payouts.model_from_rules(IME)
        now = wib(2026, 10, 9, 12)
        self.assertEqual(earn_state(IME, m, [{"posted_at": wib(2026, 10, 3)}], now)["code"], "week_closed")   # W1 closed
        self.assertIsNone(earn_state(IME, m, [{"posted_at": wib(2026, 10, 8, 9)}], now))                      # W2 open
        self.assertEqual(earn_state(IME, m, [{"posted_at": wib(2026, 9, 30)}], now)["code"], "week_closed")   # outside weeks
        self.assertIsNone(earn_state(IME, m, [], now))                                                        # unposted, inside W2

    def test_unposted_outside_weeks_and_campaign_ended(self):
        m = payouts.model_from_rules(IME)
        self.assertEqual(earn_state(IME, m, [], wib(2026, 10, 30, 10))["label"], "Week closed")
        ended = {**FANDRA, "period": {"start": "2026-09-30", "end": "2026-10-05"}}
        self.assertEqual(earn_state(ended, payouts.model_from_rules(ended), [], wib(2026, 10, 9))["label"], "Campaign ended")
        self.assertIsNone(earn_state(FANDRA, payouts.model_from_rules(FANDRA), [], wib(2026, 10, 9)))


if __name__ == "__main__":
    unittest.main()
