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


FIX = Path(__file__).resolve().parent / "fixtures" / "briefs"
ENGLISH = (FIX / "english-cpm-sample.txt").read_text(encoding="utf-8")
PROSE = (FIX / "english-prose-sample.txt").read_text(encoding="utf-8")
FAKE_AI = {  # what a utility model returns for the prose sample (shape of AI_SCHEMA)
    "name": "Night Shift Gaming", "category": "creator",
    "platforms": ["Instagram Reels", "Facebook Reels", "TikTok"], "currency": "USD",
    "payout_model": "cpm", "rate": 2.5, "block_views": 0, "min_views": 5000, "max_paid_views_per_post": 0,
    "max_payout_per_post": 250, "total_budget": 0, "hashtags": ["nightshift", "#nsgclips"],
    "mentions": [], "watermark": "not_stated", "min_length_seconds": 0, "max_length_seconds": 0,
    "start_date": "", "end_date": "2026-11-30", "source_channels": [],
    "requirements": ["Subtitles burned into the video", "Credit the streamer in the caption"],
    "content_rules": [{"id": "no_sara_or_insults", "text": "Nothing hateful"},
                      {"id": "other", "text": "No gambling content"},
                      {"id": "no_misleading_context", "text": "Don't put words in people's mouths"}],
}


class EnglishPatterns(unittest.TestCase):
    def test_cpm_sample_is_covered_by_patterns(self):
        calls = []
        r = parse_brief(ENGLISH, today=TODAY, ai=lambda p, s: calls.append(p) or {})
        self.assertEqual(calls, [])  # nothing left for the AI
        self.assertEqual(r["platforms"], ["youtube", "tiktok", "instagram"])
        self.assertEqual(r["payout"]["model"], "cpm")
        self.assertEqual((r["payout"]["rate_per_1000"], r["payout"]["currency"]), (1.5, "USD"))
        self.assertEqual(r["payout"]["max_payout_per_video"], 300)
        self.assertEqual(r["min_views_to_qualify"], 10_000)
        self.assertEqual(r["budget"], {"currency": "USD", "total": 6000})
        self.assertEqual(r["video"], {"min_seconds": 20, "max_seconds": 60})
        self.assertEqual(r["mentions"], ["@buildroompod"])
        self.assertEqual([x["channel"] for x in r["sources"]], ["@BuildRoomPod", "@BuildRoomLive"])
        self.assertEqual(r["watermark"], {"required": False, "forbidden": True})
        self.assertEqual(r["period"]["end"], "2026-10-31")
        self.assertEqual(r["requirements"], [{"id": "burned_in_captions", "text": "Burned-in captions required"}])
        self.assertEqual({c["id"] for c in r["content_rules"]}, {"no_sara_or_insults", "no_sensitive_issues"})
        m = payouts.model_from_rules(r)
        self.assertIsInstance(m, payouts.Cpm)
        self.assertEqual(payouts.payout_for(m, 9_999), 0)
        self.assertEqual(str(payouts.payout_for(m, 123_456)), "185.18")
        self.assertEqual(payouts.format_with_idr(payouts.payout_for(m, 400_000), "USD"), "$300.00 (~Rp 4.950.000)")

    def test_indonesian_briefs_get_min_views_and_no_noise_requirements(self):
        for slug, mv in (("ime-roleplay", 40_000), ("fandra-octo", 3_000)):
            got, _ = load(slug)
            self.assertEqual(got["min_views_to_qualify"], mv)
            self.assertEqual(got["requirements"], [])


class AIFallback(unittest.TestCase):
    def test_not_called_when_patterns_cover_the_brief(self):
        calls = []
        for slug in ("ime-roleplay", "fandra-octo", "motionklip-windah"):
            r = parse_brief_file(CAMPAIGNS / f"{slug}.md", today=TODAY, ai=lambda p, s: calls.append(p) or {})
            self.assertNotIn("ai_derived", r, slug)
        self.assertEqual(calls, [])

    def test_prose_brief_fills_gaps_and_marks_everything(self):
        seen = {}
        r = parse_brief(PROSE, today=TODAY, ai=lambda prompt, schema: seen.update(p=prompt, s=schema) or FAKE_AI)
        self.assertIn("payout rate not recognised", r["ai_reasons"])
        self.assertIn("requirements", seen["s"]["properties"])
        self.assertIn('"requirements" (array of strings)', seen["p"])  # keys spelled out in the prompt
        self.assertEqual(r["platforms"], ["instagram", "facebook", "tiktok"])
        self.assertEqual((r["payout"]["model"], r["payout"]["rate_per_1000"], r["payout"]["currency"]), ("cpm", 2.5, "USD"))
        self.assertEqual(r["min_views_to_qualify"], 5_000)
        self.assertEqual(r["payout"]["min_views"], 5_000)
        self.assertEqual(r["hashtags"]["required_in_order"], ["#nightshift", "#nsgclips"])
        self.assertEqual([q["id"] for q in r["requirements"]], ["burned_in_captions", "credit_creator"])
        self.assertTrue(all(q.get("ai") for q in r["requirements"]))
        ai_unsure = {u["field"] for u in r["unsure"] if u.get("source") == "ai"}
        self.assertEqual(set(r["ai_derived"]), ai_unsure)
        for f in ("platforms", "payout", "min_views_to_qualify", "hashtags", "requirements.burned_in_captions",
                  "requirements.credit_creator", "content_rules.custom_no_gambling_content", "period"):
            self.assertIn(f, ai_unsure)
        fields = [u["field"] for u in r["unsure"]]
        self.assertEqual(fields.count("payout"), 1)  # AI note replaced the pattern's "not found"
        m = payouts.model_from_rules(r)
        self.assertEqual((type(m).__name__, m.currency, m.min_views), ("Cpm", "USD", 5_000))
        self.assertEqual(payouts.format_with_idr(payouts.payout_for(m, 9_920), "USD", usd_idr=16_000), "$24.80 (~Rp 396.800)")
        self.assertEqual(payouts.payout_for(m, 4_960), 0)  # below the 5,000 minimum

    def test_currency_from_text_when_ai_omits_it(self):
        r = parse_brief("Promo\nWe pay $2 for each 1000 plays.\n", today=TODAY,
                        ai=lambda p, s: {**FAKE_AI, "currency": "", "min_views": 0})
        self.assertEqual(r["payout"]["currency"], "USD")

    def test_ai_failure_keeps_pattern_result(self):
        def boom(prompt, schema):
            raise RuntimeError("provider down")
        r = parse_brief(PROSE, today=TODAY, ai=boom)
        self.assertEqual(r["payout"]["model"], "unknown")
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
