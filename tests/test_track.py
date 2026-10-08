"""shared/track.py (P3 part 8): `python3 -m unittest tests.test_track` — real IME/Fandra rules + a USD CPM campaign."""
import json
import unittest
from pathlib import Path

from shared import track

ROOT = Path(__file__).resolve().parents[1]
RULES = {s: json.loads((ROOT / f"docs/campaigns/{s}.rules.json").read_text()) for s in ("ime-roleplay", "fandra-octo")}
RULES["usd-cpm"] = {"name": "USD CPM", "payout": {"currency": "USD", "model": "cpm", "rate_per_1000": 1.5}}


def post(i, **o):
    return {"id": f"p{i}", "status": "posted", "platform": "tiktok", "campaign": "ime-roleplay", "views": 0, "title": f"Clip {i}", **o}


class TrackTest(unittest.TestCase):
    def build(self, posts):
        return track.build(posts, RULES.get, usd_idr=16500)

    def test_states_and_totals(self):
        d = self.build([
            post(1, views=41000),                                              # IME posted ≥ 40k → Rp 200.000 estimate, at cap
            post(2, views=12000, status="claimed", expected_rp=200000),         # claimed → stored expected
            post(3, views=50000, status="paid", paid_rp=200000),                # paid → paid_rp, never "at cap"
            post(4, views=7000, campaign="fandra-octo", platform="youtube"),   # 2 full 3.000 blocks → Rp 24.000
            post(5, status="planned", views=999999),                            # not live: ignored
            post(6, status="dropped", views=999999),
        ])
        t = d["tiles"]
        self.assertEqual((t["posts"], t["views"], t["claimed"], t["paid"], t["at_cap"]), (4, 110000, 2, 1, 1))
        self.assertEqual(t["paid_fmt"], "Rp 200.000")
        self.assertEqual(t["expected_fmt"], "Rp 424.000")
        self.assertEqual(t["views_fmt"], "110.000")

    def test_breakdowns_and_top(self):
        d = self.build([post(1, views=41000), post(4, views=7000, campaign="fandra-octo", platform="youtube"), post(7, views=500, campaign=None)])
        self.assertEqual([c["name"] for c in d["campaigns"]][:2], [RULES["ime-roleplay"]["name"], RULES["fandra-octo"]["name"]])
        self.assertEqual(d["campaigns"][-1]["name"], "No campaign")
        self.assertEqual([p["name"] for p in d["platforms"]], ["TikTok", "YouTube Shorts"])
        self.assertEqual([x["title"] for x in d["top"]], ["Clip 1", "Clip 4", "Clip 7"])
        self.assertEqual(d["top"][1]["amount_fmt"], "Rp 24.000")
        self.assertEqual(d["top"][2]["amount_fmt"], "—")                      # no campaign → unknown

    def test_usd_shows_with_idr_and_counts_in_totals(self):
        d = self.build([post(1, campaign="usd-cpm", views=10000)])             # 10 × $1.50 = $15.00
        self.assertEqual(d["top"][0]["amount_fmt"], "$15.00 (~Rp 247.500)")
        self.assertEqual(d["tiles"]["expected_rp"], 247500)
        self.assertEqual(d["skipped_currencies"], [])


if __name__ == "__main__":
    unittest.main()
