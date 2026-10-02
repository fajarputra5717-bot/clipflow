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


ENGLISH = (Path(__file__).resolve().parent / "fixtures" / "briefs" / "english-cpm-sample.txt").read_text(encoding="utf-8")
FAKE_AI = {  # what a utility model returns for the English sample (shape of AI_SCHEMA)
    "name": "The Build Room Podcast: Clipping Campaign", "category": "creator",
    "platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"], "currency": "USD",
    "payout_model": "cpm", "rate": 1.5, "block_views": 0, "min_views": 10000, "max_paid_views_per_post": 0,
    "max_payout_per_post": 300, "total_budget": 6000, "hashtags": ["#buildroom", "founderclips"],
    "mentions": ["buildroompod"], "watermark": "forbidden", "min_length_seconds": 20, "max_length_seconds": 60,
    "start_date": "", "end_date": "2026-10-31", "source_channels": ["@BuildRoomPod", "youtube.com/@BuildRoomLive"],
    "content_rules": [{"id": "no_sara_or_insults", "text": "Don't make fun of guests"},
                      {"id": "other", "text": "No politics"},
                      {"id": "other", "text": "Burned-in captions required"}],
}


class AIFallback(unittest.TestCase):
    def test_not_called_when_patterns_cover_the_brief(self):
        calls = []
        for slug in ("ime-roleplay", "fandra-octo", "motionklip-windah"):
            r = parse_brief_file(CAMPAIGNS / f"{slug}.md", today=TODAY, ai=lambda p, s: calls.append(p) or {})
            self.assertNotIn("ai_derived", r, slug)
        self.assertEqual(calls, [])

    def test_english_cpm_brief_fills_gaps_and_marks_everything(self):
        seen = {}
        r = parse_brief(ENGLISH, today=TODAY, ai=lambda prompt, schema: seen.update(p=prompt, s=schema) or FAKE_AI)
        self.assertIn("payout rate not recognised", r["ai_reasons"])
        self.assertIn("BRIEF:", seen["p"])
        self.assertEqual(r["platforms"], ["youtube", "tiktok", "instagram"])
        self.assertEqual(r["payout"]["model"], "per_block")
        self.assertEqual((r["payout"]["per_block"], r["payout"]["block_views"], r["payout"]["currency"]), (1.5, 1000, "USD"))
        self.assertEqual(r["payout"]["max_payout_per_video"], 300)
        self.assertEqual(r["mentions"], ["@buildroompod"])
        self.assertEqual(r["watermark"], {"required": False, "forbidden": True})
        self.assertEqual(r["video"], {"min_seconds": 20, "max_seconds": 60})
        self.assertEqual(r["period"]["end"], "2026-10-31")
        # watermark + deadline come from the English patterns, not the AI
        self.assertNotIn("watermark", r["ai_derived"])
        self.assertNotIn("period", r["ai_derived"])
        # one unsure entry per field: the AI's replaces the pattern's "not found"
        fields = [u["field"] for u in r["unsure"]]
        self.assertEqual(fields.count("platforms"), 1)
        self.assertEqual(fields.count("payout"), 1)
        self.assertEqual([s["channel"] for s in r["sources"]], ["@BuildRoomPod", "@BuildRoomLive"])
        # patterns win: the hashtag line was matched by regex, so the AI's list is ignored
        self.assertEqual(r["hashtags"]["required_in_order"], ["#buildroom", "#founderclips"])
        self.assertNotIn("hashtags", r["ai_derived"])
        # every AI-filled field is in ai_derived AND unsure (source ai)
        ai_unsure = {u["field"] for u in r["unsure"] if u.get("source") == "ai"}
        self.assertEqual(set(r["ai_derived"]), ai_unsure)
        for f in ("platforms", "payout", "mentions", "video", "sources",
                  "content_rules.no_sara_or_insults", "content_rules.custom_no_politics"):
            self.assertIn(f, ai_unsure)
        self.assertTrue(all(c.get("ai") for c in r["content_rules"]))
        # USD isn't modelled by payouts.py (IDR only) -> Unknown, not silently wrong
        self.assertIsInstance(payouts.model_from_rules(r), payouts.Unknown)

    def test_currency_from_text_when_ai_omits_it(self):
        r = parse_brief(ENGLISH, today=TODAY, ai=lambda p, s: {**FAKE_AI, "currency": ""})
        self.assertEqual(r["payout"]["currency"], "USD")
        self.assertEqual(r["budget"], {"currency": "USD", "total": 6000})

    def test_ai_failure_keeps_pattern_result(self):
        def boom(prompt, schema):
            raise RuntimeError("provider down")
        r = parse_brief(ENGLISH, today=TODAY, ai=boom)
        self.assertEqual(r["hashtags"]["required_in_order"], ["#buildroom", "#founderclips"])
        self.assertTrue(any(u["field"] == "ai" and "provider down" in u["why"] for u in r["unsure"]))

    def test_idr_ai_payout_feeds_payouts(self):
        ai = lambda p, s: {"platforms": ["tiktok"], "payout_model": "fixed_threshold", "currency": "IDR",
                           "rate": 150000, "min_views": 30000, "hashtags": [], "content_rules": []}
        r = parse_brief("Promo X\nPay 150rb kalau tembus 30rb views\n", today=TODAY, ai=ai)
        m = payouts.model_from_rules(r)
        self.assertEqual((type(m).__name__, m.amount, m.min_views), ("FixedThreshold", 150000, 30000))
        self.assertIn("payout", r["ai_derived"])


if __name__ == "__main__":
    unittest.main()
