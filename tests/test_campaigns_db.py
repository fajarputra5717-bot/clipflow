"""shared/campaigns.py DB loader (P3 part 1, 157). Run: python3 -m unittest tests.test_campaigns_db"""
import os
import unittest

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")  # before shared.campaigns is imported (it reads it once)
from shared import campaigns as c  # noqa: E402

ROWS = [
    {"slug": "ime-roleplay", "name": "IME (DB)", "rules": {"platforms": ["tiktok"], "hashtags": {"required_in_order": ["#a"]}},
     "brief_text": "brief", "created_by": "u-admin", "visibility": "shared", "paused": False},
    {"slug": "secret", "name": "Mine", "rules": {}, "brief_text": "", "created_by": "u-1", "visibility": "private", "paused": True},
]


class DbLoader(unittest.TestCase):
    def tearDown(self):
        c.set_db_loader(None)

    def test_rows_become_rules(self):
        c.set_db_loader(lambda: ROWS)
        ime, sec = c.get("ime-roleplay"), c.get("secret")
        self.assertEqual((c.display_name(ime), c.hashtags(ime), ime["brief_pending"]), ("IME (DB)", ["#a"], False))
        self.assertEqual((sec["brief_pending"], sec["paused"], sec["visibility"]), (True, True, "private"))
        self.assertIsNone(c.get("fandra-octo"))          # the DB, not the files, once a loader is set

    def test_visibility(self):
        c.set_db_loader(lambda: ROWS)
        sec = c.get("secret")
        self.assertTrue(c.visible_to(sec, {"id": "u-1", "role": "member"}))
        self.assertTrue(c.visible_to(sec, {"id": "u-9", "role": "admin"}))
        self.assertFalse(c.visible_to(sec, {"id": "u-2", "role": "member"}))
        self.assertTrue(c.visible_to(c.get("ime-roleplay"), {"id": "u-2", "role": "member"}))
        self.assertFalse(c.visible_to(None, {"id": "u-2", "role": "member"}))

    def test_db_error_falls_back_to_files(self):
        def boom():
            raise RuntimeError("db down")
        c.set_db_loader(boom, log=lambda m: None)
        self.assertIn("fandra-octo", c.load_all())

    def test_cache_and_invalidate(self):
        calls = []
        c.set_db_loader(lambda: calls.append(1) or ROWS)
        c.load_all(); c.load_all()
        self.assertEqual(len(calls), 1)
        c.invalidate(); c.load_all()
        self.assertEqual(len(calls), 2)

    def test_seed_rows_from_files(self):
        rows = {r["slug"]: r for r in c.seed_rows()}
        self.assertIn("ime-roleplay", rows)
        self.assertTrue(rows["ime-roleplay"]["brief_text"])
        self.assertNotIn("brief_pending", rows["ime-roleplay"]["rules"])


if __name__ == "__main__":
    unittest.main()
