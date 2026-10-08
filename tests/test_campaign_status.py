"""shared/campaign_status.py on the real rules (P3 part 2, 158). Run: python3 -m unittest tests.test_campaign_status"""
import os
import unittest
from datetime import datetime

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")  # before shared.campaigns is imported (it reads it once)
from shared import campaign_status as cs, campaigns, payouts  # noqa: E402


def wib(*a):
    return datetime(*a, tzinfo=payouts.WIB)


class Ime(unittest.TestCase):
    R = campaigns.get("ime-roleplay")

    def test_weeks(self):
        self.assertEqual(cs.current_week(self.R, wib(2026, 10, 7, 20))["id"], "W1")
        self.assertEqual(cs.current_week(self.R, wib(2026, 10, 7, 20))["days_left"], 1)
        self.assertEqual(cs.current_week(self.R, wib(2026, 10, 8, 0, 5)), {"id": "W2", "start": "2026-10-08", "end": "2026-10-14", "days_left": 7})
        self.assertIsNone(cs.current_week(self.R, wib(2026, 10, 30)))

    def test_status_through_october(self):
        self.assertEqual(cs.status(self.R, wib(2026, 10, 7))["code"], "active")
        self.assertEqual(cs.status(self.R, wib(2026, 10, 7))["detail"], "Week 1 · 1 day left")
        self.assertEqual(cs.status(self.R, wib(2026, 10, 25))["code"], "active")
        s = cs.status(self.R, wib(2026, 10, 26))
        self.assertEqual((s["code"], s["days_left"], s["last_day"]), ("ending_soon", 3, "2026-10-28"))
        self.assertEqual(cs.status(self.R, wib(2026, 10, 28, 23, 59))["code"], "ending_soon")
        for d in (29, 30, 31):   # outside W1–W4: ended for posting
            s = cs.status(self.R, wib(2026, 10, d))
            self.assertEqual((s["code"], s["label"], s["detail"]), ("ended", "Ended", "Ended 28 Oct"))

    def test_clip_labels(self):
        self.assertEqual(cs.clip_labels(self.R, [], wib(2026, 10, 9)), {"earn": None, "expired": False})
        posted_w1 = [{"posted_at": wib(2026, 10, 3, 12)}]
        self.assertEqual(cs.clip_labels(self.R, posted_w1, wib(2026, 10, 9))["earn"]["label"], "Week closed")
        self.assertEqual(cs.clip_labels(self.R, [], wib(2026, 10, 30)),
                         {"earn": {"code": "campaign_ended", "label": "Campaign ended"}, "expired": True})
        self.assertEqual(cs.clip_labels(None, [], wib(2026, 10, 30)), {"earn": None, "expired": False})

    def test_paused_wins(self):
        self.assertEqual(cs.status({**self.R, "paused": True}, wib(2026, 10, 7))["label"], "Paused")


class Fandra(unittest.TestCase):
    R = campaigns.get("fandra-octo")

    def test_open_ended_is_active(self):
        for d in (wib(2026, 10, 7), wib(2027, 6, 1)):
            s = cs.status(self.R, d)
            self.assertEqual((s["code"], s["last_day"], s["days_left"]), ("active", None, None))
        self.assertIsNone(cs.current_week(self.R, wib(2026, 10, 7)))


if __name__ == "__main__":
    unittest.main()
