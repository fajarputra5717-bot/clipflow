"""Unit tests for shared/brief_parser.py on the saved briefs. Run: python -m unittest tests.test_brief_parser"""

import json
import unittest
from datetime import date
from pathlib import Path

from shared import payouts
from shared.brief_parser import parse_brief, parse_brief_file

CAMPAIGNS = Path(__file__).resolve().parent.parent / "docs" / "campaigns"
TODAY = date(2026, 10, 2)


def load(slug):
    return (parse_brief_file(CAMPAIGNS / f"{slug}.md", today=TODAY),
            json.loads((CAMPAIGNS / f"{slug}.rules.json").read_text(encoding="utf-8")))


def rule_ids(rules):
    return {r["id"] for r in (rules.get("content_rules") or rules.get("forbidden") or [])}


def unsure_fields(rules):
    return [u["field"] for u in rules["unsure"]]


class SavedBriefs(unittest.TestCase):
    def test_ime_matches_hand_made_rules(self):
        got, saved = load("ime-roleplay")
        self.assertEqual(payouts.model_from_rules(got), payouts.model_from_rules(saved))
        self.assertEqual(got["platforms"], saved["platforms"])
        self.assertEqual(got["hashtags"]["required_in_order"], saved["hashtags"]["required_in_order"])
        self.assertEqual(rule_ids(got), rule_ids(saved))
        self.assertEqual(got["budget"]["total_per_month"], 20_000_000)
        self.assertEqual(got["budget"]["per_refill"], 5_000_000)
        self.assertEqual(got["weeks"]["list"], saved["weeks"]["list"])
        self.assertEqual(got["weeks"]["refill_time"], "00:00")
        self.assertEqual(got["content"]["title_examples"][0], "Gak Nyangka Endingnya Begini...")
        self.assertEqual(got["content"]["brand_socials"], saved["content"]["brand_socials"])
        self.assertTrue(got["watermark"]["required"])
        self.assertEqual(got["manual_only"][0]["id"], "discord_tag")
        self.assertEqual(got["payout"]["claim_form"], saved["payout"]["claim_form"])
        # what the admin had to answer is exactly what the parser is unsure about
        for f in ("limits.account_unit", "budget.carry_over", "weeks.outside", "period", "sources",
                  "watermark.asset_id"):
            self.assertIn(f, unsure_fields(got))
        self.assertNotIn("content_rules", unsure_fields(got))
        self.assertEqual(len(unsure_fields(got)), len(set((u["field"], u["why"]) for u in got["unsure"])))

    def test_fandra_matches_hand_made_rules(self):
        got, saved = load("fandra-octo")
        m = payouts.model_from_rules(got)
        self.assertEqual(m, payouts.model_from_rules(saved))
        self.assertEqual(payouts.max_payout(m), 1_992_000)
        self.assertEqual(got["platforms"], saved["platforms"])
        self.assertEqual(got["hashtags"]["required_in_order"], saved["hashtags"]["required_in_order"])
        self.assertEqual(rule_ids(got), rule_ids(saved))
        self.assertEqual(got["sources"], [{"platform": "youtube", "channel": "@FandraOcto", "job_source": True}])
        self.assertEqual(got["period"], {"start": "2026-09-30", "end": None, "until": "budget runs out"})
        self.assertEqual(got["payout"]["payment_methods"], ["GoPay", "DANA"])
        self.assertEqual((got["payout"]["claims_per_video"], got["payout"]["views_counted"]), (1, "at submit time"))
        self.assertEqual(got["creator_socials"]["youtube"], "https://www.youtube.com/@FandraOcto")
        # the same open questions the hand-made file lists
        for f in ("payout.rounding", "budget.total", "period.start"):
            self.assertIn(f, unsure_fields(got))

    def test_motionklip_pending_brief_is_all_unsure(self):
        got, _ = load("motionklip-windah")
        self.assertTrue(got["brief_pending"])
        self.assertIsInstance(payouts.model_from_rules(got), payouts.Unknown)
        self.assertEqual(unsure_fields(got), ["*"])


class Edges(unittest.TestCase):
    def test_no_rate_is_unknown_and_unsure(self):
        r = parse_brief("Some Campaign\nPlatform: TikTok\nHashtag\n#a #b\n", today=TODAY)
        self.assertEqual(r["payout"]["model"], "unknown")
        self.assertIsInstance(payouts.model_from_rules(r), payouts.Unknown)
        self.assertIn("payout", unsure_fields(r))
        self.assertIn("hashtags.order", unsure_fields(r))

    def test_unrecognised_rule_line_is_reported(self):
        r = parse_brief("X\n* Dilarang memakai musik berhak cipta.\n", today=TODAY)
        self.assertTrue(any("musik berhak cipta" in u["why"] for u in r["unsure"]))

    def test_no_watermark_brief(self):
        r = parse_brief("X\nPlatform: TikTok\n* Dilarang menambahkan watermark apapun.\n", today=TODAY)
        self.assertEqual(r["watermark"], {"required": False, "forbidden": True})


if __name__ == "__main__":
    unittest.main()
