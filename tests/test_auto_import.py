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
    return auto_import.skip_reason(it, rules, enabled_at=kw.pop("enabled_at", ON), now=NOW, min_seconds=300, **kw)


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
        self.assertIsNone(why(item(duration=None)))            # unknown duration: import, the pipeline decides

    def test_skips(self):
        self.assertEqual(why(item(duration=120)), "Under 5 min")
        self.assertEqual(why(item(published_at=(ON - timedelta(hours=13)).isoformat())), "Uploaded before auto-import was on")
        self.assertIsNone(why(item(published_at=(ON - timedelta(hours=11)).isoformat())))   # stream started just before
        self.assertEqual(why(item(published_at="2026-09-29T10:00:00+00:00"), enabled_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
                         "Uploaded before the campaign started")
        self.assertEqual(why(item(), rules={**FANDRA, "paused": True}), "Campaign paused")
        self.assertEqual(why(item(), rules={**FANDRA, "period": {"start": "2026-09-01", "end": "2026-10-01"}}), "Campaign ended")

    def test_no_upload_time(self):
        self.assertIsNone(why(item(published_at=None)))                       # feed hiccup on a fresh check: import
        self.assertEqual(why(item(published_at=None), stale=True), "Older than the watch")


if __name__ == "__main__":
    unittest.main()
