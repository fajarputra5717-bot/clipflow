"""shared/schedule.py (P2.5 S1): run with `CAMPAIGNS_DIR=docs/campaigns python3 -m unittest tests.test_schedule`."""
import json
import os
import unittest
from datetime import datetime, timezone

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")

from shared import campaigns, schedule as s  # noqa: E402
from shared.settings import DEFAULT_SETTINGS  # noqa: E402

WIB = s.WIB


def wib(*a):
    return datetime(*a, tzinfo=WIB)


class Normalize(unittest.TestCase):
    def test_defaults_are_valid_and_owner_approved(self):
        t = s.normalize_posting_times(DEFAULT_SETTINGS["POSTING_TIMES"])
        self.assertEqual(t, {"tiktok": ["12:00", "19:00", "21:00"], "instagram": ["11:30", "19:30"],
                             "youtube": ["17:00", "20:00"], "facebook": ["12:00", "19:00"]})

    def test_cleans_sorts_dedupes(self):
        self.assertEqual(s.normalize_posting_times({"tiktok": ["9:05", "21:00", "09:05", " 07:30 "]}),
                         {"tiktok": ["07:30", "09:05", "21:00"]})
        self.assertEqual(s.normalize_posting_times(json.dumps({"x": []})), {"x": []})

    def test_rejects(self):
        for bad in ('{"myspace": ["12:00"]}', '{"tiktok": ["24:00"]}', '{"tiktok": ["7pm"]}', '{"tiktok": "12:00"}',
                    "[1]", "not json", json.dumps({"tiktok": [f"{h:02d}:00" for h in range(9)]})):
            with self.assertRaises(ValueError, msg=bad):
                s.normalize_posting_times(bad)

    def test_parse_is_lenient(self):
        self.assertEqual(s.parse_posting_times("broken", '{"youtube": ["20:00"]}'), {"youtube": ["20:00"]})
        self.assertEqual(s.parse_posting_times(None, None), {})


class NextSlots(unittest.TestCase):
    T = {"tiktok": ["12:00", "19:00", "21:00"], "youtube": []}

    def test_next_three_after_now_in_utc(self):
        got = s.next_slots(self.T, "tiktok", wib(2026, 10, 7, 13, 0))
        self.assertEqual([g.astimezone(WIB) for g in got], [wib(2026, 10, 7, 19), wib(2026, 10, 7, 21), wib(2026, 10, 8, 12)])
        self.assertTrue(all(g.tzinfo == timezone.utc for g in got))
        self.assertEqual(got[0], datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc))   # 19:00 WIB = 12:00 UTC

    def test_strictly_after_and_wraps_midnight(self):
        got = s.next_slots(self.T, "tiktok", wib(2026, 10, 7, 21, 0), n=2)
        self.assertEqual([g.astimezone(WIB) for g in got], [wib(2026, 10, 8, 12), wib(2026, 10, 8, 19)])

    def test_skips_taken_same_minute(self):
        taken = [datetime(2026, 10, 7, 12, 0, 30, tzinfo=timezone.utc)]   # 19:00:30 WIB
        got = s.next_slots(self.T, "tiktok", wib(2026, 10, 7, 13), taken, n=1)
        self.assertEqual(got[0].astimezone(WIB), wib(2026, 10, 7, 21))

    def test_no_times_no_slots(self):
        self.assertEqual(s.next_slots(self.T, "youtube", wib(2026, 10, 7)), [])
        self.assertEqual(s.next_slots(self.T, "facebook", wib(2026, 10, 7)), [])

    def test_naive_after_rejected(self):
        with self.assertRaises(ValueError):
            s.next_slots(self.T, "tiktok", datetime(2026, 10, 7))

    def test_ime_skips_29_to_31_oct(self):
        ime = campaigns.get("ime-roleplay")
        got = s.next_slots(self.T, "tiktok", wib(2026, 10, 28, 20), rules=ime, n=5)
        self.assertEqual([g.astimezone(WIB) for g in got], [wib(2026, 10, 28, 21)])   # W4 ends 28 Oct; 29–31 out

    def test_fandra_open_ended_is_never_cut(self):
        fandra = campaigns.get("fandra-octo")
        self.assertEqual(len(s.next_slots(self.T, "tiktok", wib(2026, 12, 30, 22), rules=fandra, n=3)), 3)
        self.assertEqual(s.next_slots(self.T, "tiktok", wib(2026, 9, 25), rules=fandra, n=1)[0].astimezone(WIB),
                         wib(2026, 9, 30, 12))   # period starts 30 Sep


if __name__ == "__main__":
    unittest.main()
