"""rule_checks with the editor (P4): length after cuts + one-click fixes. Run: python -m unittest tests.test_rule_checks_editor"""

import os
import unittest

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")  # before shared.campaigns is imported (it reads it once)
from shared import rule_checks as rc  # noqa: E402

RULES = {"platforms": ["tiktok", "facebook"], "hashtags": {"required_in_order": ["#a", "#b"]},
         "watermark": {"required": True, "asset_name": "Motion Klip"}}


def cand(**kw):
    c = {"start_time": 6.0, "end_time": 102.0, "description": "x #a #b", "render_warnings": [], "edit_spec": None}
    c.update(kw)
    return c


def chip(chips, cid):
    return next(ch for ch in chips if ch["id"] == cid)


class Length(unittest.TestCase):
    def test_too_long_offers_trim_to_strictest_limit_minus_margin(self):
        ch = chip(rc.check(RULES, cand()), "length")                   # 96 s > Facebook 90
        self.assertFalse(ch["ok"])
        self.assertEqual((ch["fix"], ch["fix_target"]), ("trim", 88))
        self.assertIn("too long for Facebook Reels", ch["label"])

    def test_cuts_count_toward_the_length(self):
        spec = {"cuts": {"trim": [0.0, 88.0], "removed": [[10.0, 12.0]]}}
        ch = chip(rc.check(RULES, cand(edit_spec=spec)), "length")      # 88 - 2 = 86 s
        self.assertTrue(ch["ok"])
        self.assertEqual(ch["label"], "Length 86 s")
        self.assertIsNone(ch["fix"])

    def test_too_short_has_no_trim_fix(self):
        ch = chip(rc.check(RULES, cand(end_time=7.0)), "length")        # 1 s < 3 s
        self.assertFalse(ch["ok"])
        self.assertIsNone(ch["fix"])
        self.assertIn("too short", ch["label"])


class Watermark(unittest.TestCase):
    def test_missing_campaign_watermark_offers_rerender(self):
        warn = [{"code": "campaign_watermark", "message": "could not be resolved"}]
        self.assertEqual(chip(rc.check(RULES, cand(render_warnings=warn)), "watermark")["fix"], "rerender")
        self.assertIsNone(chip(rc.check(RULES, cand()), "watermark")["fix"])


if __name__ == "__main__":
    unittest.main()
