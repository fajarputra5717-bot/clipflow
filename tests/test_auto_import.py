"""shared/auto_import.py (P3 part 7): `python3 -m unittest tests.test_auto_import` — real Fandra/MotionKlip rules."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared import auto_import

ROOT = Path(__file__).resolve().parents[1]
FANDRA = json.loads((ROOT / "docs/campaigns/fandra-octo.rules.json").read_text())
WINDAH = json.loads((ROOT / "docs/campaigns/motionklip-windah.rules.json").read_text())
NOW = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
ON = NOW - timedelta(days=2)


def item(**o):
    return {"video_id": "v1", "url": "https://www.youtube.com/watch?v=v1", "title": "Stream", "duration": 3600,
            "published_at": (NOW - timedelta(hours=1)).isoformat(), **o}


def why(it, rules=FANDRA, **kw):
    return auto_import.skip_reason(it, rules, enabled_at=kw.pop("enabled_at", ON), now=NOW, **kw)


class AutoImportTest(unittest.TestCase):
    def test_channel_key_and_watchable(self):
        self.assertEqual(auto_import.channel_key("@FandraOcto"), "https://www.youtube.com/@fandraocto")
        self.assertEqual(auto_import.channel_key("https://youtube.com/@FandraOcto/streams"), "https://www.youtube.com/@fandraocto")
        cid = "UC" + "a" * 22
        self.assertEqual(auto_import.channel_key(cid), f"https://www.youtube.com/channel/{cid}")
        self.assertEqual([w["label"] for w in auto_import.watchable(WINDAH)], ["@windahbasudara", "@brandochillgames"])
        self.assertEqual(auto_import.watchable(FANDRA)[0]["content"][:10], "livestream")
        bad = {"sources": [{"platform": "tiktok", "channel": "@x"}, {"channel": "not a channel"}, {"channel": "@FandraOcto"}, {"channel": "@fandraocto"}]}
        self.assertEqual(len(auto_import.watchable(bad)), 1)

    def test_imports_a_fresh_upload(self):
        self.assertIsNone(why(item()))
        self.assertEqual(why(item(duration=None)), "Unknown length")   # QA P3 Low: never bypasses the window

    def test_skips(self):
        self.assertEqual(why(item(duration=120)), "Under 5 min")
        self.assertEqual(why(item(published_at=(ON - timedelta(hours=13)).isoformat())), "Uploaded before auto-import was on")
        self.assertIsNone(why(item(published_at=(ON - timedelta(hours=11)).isoformat())))   # stream started just before
        self.assertEqual(why(item(published_at="2026-09-29T10:00:00+00:00"), enabled_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
                         "Uploaded before the campaign started")
        self.assertEqual(why(item(), rules={**FANDRA, "paused": True}), "Campaign paused")
        self.assertEqual(why(item(), rules={**FANDRA, "period": {"start": "2026-09-01", "end": "2026-10-01"}}), "Campaign ended")

    def test_no_upload_time(self):
        self.assertEqual(why(item(published_at=None)), "No upload time")      # QA P3 Medium: never imported blind
        self.assertEqual(why(item(published_at=None), stale=True), "Older than the watch")


class ConfirmableTest(unittest.TestCase):
    def test_reasons_match(self):   # 187: the confirm list keys off these exact strings
        stale = why(item(published_at=None), stale=True)
        for r in (why(item(published_at=None)), stale, why(item(duration=None))):
            self.assertIn(r, auto_import.CONFIRMABLE)
        self.assertNotIn(why(item(duration=120)), auto_import.CONFIRMABLE)


class GuardrailTest(unittest.TestCase):
    def g(self, **raw):
        return auto_import.normalize_guardrails(raw)

    def test_defaults_and_describe(self):
        g = self.g()
        self.assertEqual((g["max_per_day"], g["min_minutes"], g["max_minutes"], g["pause_below_gb"], g["telegram_note"]), (2, 5, 240, None, True))
        self.assertEqual(auto_import.describe(g), "Max 2 a day · 5 min–4 h · Telegram note")
        g2 = self.g(include="Ranked, ranked ,  Push  Rank", exclude=["#shorts"], pause_below_gb="50", telegram_note="false", max_minutes=90)
        self.assertEqual(g2["include"], ["ranked", "push rank"])
        self.assertEqual(auto_import.describe(g2), "Max 2 a day · 5 min–1 h 30 min · only: ranked, push rank · not: #shorts · pauses below 50 GB free · no Telegram note")
        self.assertIsNone(self.g(pause_below_gb="")["pause_below_gb"])
        self.assertEqual(auto_import.normalize_guardrails({"max_per_day": 5}, base={"min_minutes": 10, "junk": 1})["min_minutes"], 10)

    def test_unknown_keys(self):   # QA Low (fresh e2e 11162f8)
        self.assertEqual(auto_import.unknown_guard_keys({"max_per_day": 3, "maxPerDay": 3, "foo": 1}), ["foo", "maxPerDay"])
        self.assertEqual(auto_import.unknown_guard_keys(None), [])

    def test_validation(self):
        for raw in ({"max_per_day": 0}, {"max_per_day": "x"}, {"min_minutes": 60, "max_minutes": 30}, {"include": ["w"] * 11 + [str(i) for i in range(11)]},
                    {"exclude": ["x" * 41]}, {"pause_below_gb": -1}):
            with self.assertRaises(ValueError, msg=raw):
                auto_import.normalize_guardrails(raw)

    def test_filters(self):
        g = self.g(include=["ranked"], exclude=["#shorts"], max_minutes=240)
        self.assertEqual(why(item(duration=5 * 3600), guard=g), "Over 4 h")
        self.assertEqual(why(item(duration=120), guard=g), "Under 5 min")
        self.assertEqual(why(item(title="Casual night"), guard=g), "Title has none of: ranked")
        self.assertEqual(why(item(title="RANKED grind #Shorts"), guard=g), "Title has '#shorts'")
        self.assertIsNone(why(item(title="Ranked grind"), guard=g))


if __name__ == "__main__":
    unittest.main()
