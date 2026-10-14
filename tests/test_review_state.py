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


class FinishedLabel(unittest.TestCase):
    """Review shows a status instead of a disabled Approve on approved clips (owner 2026-10-14)."""
    def setUp(self):
        from datetime import timezone
        from shared.review_state import finished_label
        self.f, self.utc = finished_label, timezone.utc
        self.now = datetime(2026, 10, 14, 3, 0, tzinfo=self.utc)          # Wed 10:00 WIB

    def at(self, d, h):
        return datetime(2026, 10, d, h, 0, tzinfo=self.utc)

    def test_review_and_unapproved_have_none(self):
        self.assertIsNone(self.f("review", [], self.now))
        self.assertIsNone(self.f("preview_rendering", [], self.now))

    def test_states(self):
        self.assertEqual(self.f("rendering", [], self.now), "Approved · Rendering final")
        self.assertEqual(self.f("completed", [], self.now), "Approved · Not scheduled yet")
        planned = [{"platform": "tiktok", "status": "planned", "scheduled_for": self.at(15, 10)},   # Thu 17:00 WIB
                   {"platform": "youtube", "status": "planned", "scheduled_for": self.at(14, 10)}]  # Wed 17:00 WIB
        self.assertEqual(self.f("completed", planned, self.now), "Approved · Scheduled Wed 17:00")
        far = [{"platform": "tiktok", "status": "planned", "scheduled_for": self.at(28, 10)}]
        self.assertEqual(self.f("completed", far, self.now), "Approved · Scheduled Wed 28 Oct 17:00")
        late = [{"platform": "tiktok", "status": "planned", "scheduled_for": self.at(13, 10)}]
        self.assertEqual(self.f("completed", late, self.now), "Approved · Scheduled Tue 13 Oct 17:00 (overdue)")
        dropped = [{"platform": "tiktok", "status": "dropped", "scheduled_for": self.at(15, 10)}]
        self.assertEqual(self.f("completed", dropped, self.now), "Approved · Not scheduled yet")

    def test_posted(self):
        posts = [{"platform": "tiktok", "status": "posted"}, {"platform": "youtube", "status": "planned", "scheduled_for": self.at(15, 10)}]
        self.assertEqual(self.f("completed", posts, self.now), "Posted on TikTok · next Thu 17:00")
        two = [{"platform": "tiktok", "status": "posted"}, {"platform": "instagram", "status": "claimed"}]
        self.assertEqual(self.f("completed", two, self.now), "Posted on 2 platforms")
        fb = [{"platform": "facebook", "status": "posted"}]
        self.assertEqual(self.f("completed", fb, self.now), "Posted on Facebook")   # QA Low 1
