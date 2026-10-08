"""shared/campaign_view.py on the real rules (P3 part 5, 161). Run: python3 -m unittest tests.test_campaign_view"""
import os
import unittest
from datetime import datetime

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")  # before shared.campaigns is imported (it reads it once)
from shared import campaign_status, campaign_view as v, campaigns, payouts  # noqa: E402

NOW = datetime(2026, 10, 8, 9, tzinfo=payouts.WIB)


class Ime(unittest.TestCase):
    V = v.build(campaigns.get("ime-roleplay"), NOW)

    def test_payout_and_budget(self):
        self.assertEqual(self.V["payout"][0], "Rp 200.000 per post at 40.000 views, max 2 per platform account/month")
        self.assertIn("At most Rp 2.400.000 per creator per month.", self.V["payout"])
        self.assertEqual(self.V["budget"], ["Rp 20.000.000 per month.",
                                            "Refilled 4× (Rp 5.000.000 each), every week at 00:00 WIB; first come, first served."])

    def test_weeks_open_highlighted(self):
        self.assertEqual([(w["id"], w["dates"], w["state"]) for w in self.V["weeks"]],
                         [("W1", "1–7 Oct", "closed"), ("W2", "8–14 Oct", "open"), ("W3", "15–21 Oct", "upcoming"),
                          ("W4", "22–28 Oct", "upcoming")])
        self.assertEqual(self.V["weeks"][1]["days_left"], 7)

    def test_rest(self):
        self.assertEqual(self.V["hashtags"][0], "#imeroleplay")
        self.assertEqual(self.V["watermark"], {"required": True, "name": "Motion Klip", "has_asset": True})
        self.assertTrue(any(a["topic"] == "Uploads oct 29 31" and a["date"] == "2026-10-02" for a in self.V["questions"]["answered"]))
        self.assertEqual(len(self.V["questions"]["open"]), 2)
        self.assertEqual(self.V["claim"]["form"], "https://forms.gle/VAe8gZGxUaBsxewx6")
        self.assertEqual([p["name"] for p in self.V["platforms"]][:2], ["TikTok", "YouTube Shorts"])


class Others(unittest.TestCase):
    def test_fandra(self):
        f = v.build(campaigns.get("fandra-octo"), NOW)
        self.assertEqual(f["period"], "From 30 Sep 2026, until the budget runs out")
        self.assertEqual(f["payout"][:2], ["Rp 12.000 per full 3.000 views, max Rp 1.992.000",
                                           "Only full blocks of 3.000 views pay; views above 500.000 don't count."])
        self.assertEqual(f["budget"], ["Total budget not stated; the campaign runs until it is used up."])
        self.assertEqual(f["weeks"], [])

    def test_windah_pilot(self):
        w = v.build(campaigns.get("motionklip-windah"), NOW)
        self.assertEqual((w["payout"], w["period"], w["budget"], w["claim"]), (["Payout not set yet"], None, [], None))
        self.assertEqual(campaign_status.status(campaigns.get("motionklip-windah"), NOW)["detail"], "No end date set")
        self.assertEqual(campaign_status.status(campaigns.get("fandra-octo"), NOW)["detail"], "Open until the budget runs out")


if __name__ == "__main__":
    unittest.main()
