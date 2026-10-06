"""shared/hook_ranges.py (137): python3 -m unittest tests.test_hook_ranges"""
import unittest

from shared import hook_ranges as h


class TooClose(unittest.TestCase):
    def test_start_within_10s(self):
        self.assertTrue(h.too_close((100, 140), (109, 170)))   # starts 9 s apart
        self.assertFalse(h.too_close((100, 140), (150, 190)))  # disjoint

    def test_overlap_vs_shorter(self):
        self.assertFalse(h.too_close((100, 140), (128, 168)))  # 12 s overlap = 30 % of 40: allowed (not more)
        self.assertTrue(h.too_close((100, 140), (127, 167)))   # 13 s > 30 %
        self.assertTrue(h.too_close((100, 200), (150, 160)))   # fully inside the longer one

    def test_conflict_and_merge(self):
        used = [[10, 50], [300, 340]]
        self.assertEqual(h.conflict((305, 345), used), [300, 340])
        self.assertIsNone(h.conflict((600, 640), used))
        self.assertEqual(h.merge(used, (600, 640), (10.04, 50.02)), [[10, 50], [300, 340], [600, 640]])


if __name__ == "__main__":
    unittest.main()
