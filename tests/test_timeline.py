"""shared/timeline.py (P4 task 2). Run: python -m unittest tests.test_timeline"""

import json
import tempfile
import time
import unittest
from pathlib import Path

from shared import timeline as tl

SEGS = [{"start": 0, "end": 1.46, "words": [{"word": "Kekuatan", "start": 0.36, "end": 0.94},
                                          {"word": "si", "start": 0.94, "end": 1.04}]},
        {"start": 0, "end": 0.36, "words": [{"word": "Hahahaha", "start": 0, "end": 0.36}]},
        {"start": 2.5, "end": 3.0, "words": [{"word": " hitam ", "start": 2.5, "end": 3.0}, {"word": "", "start": 3, "end": 3.1},
                                          {"word": "bad", "start": "x", "end": 1}]}]


class Words(unittest.TestCase):
    def test_flatten_sort_index(self):
        w = tl.words_from_segments(SEGS)
        self.assertEqual([x["text"] for x in w], ["Hahahaha", "Kekuatan", "si", "hitam"])
        self.assertEqual([x["i"] for x in w], [0, 1, 2, 3])
        self.assertEqual(tl.words_from_segments(None), [])

    def test_gaps(self):
        w = tl.words_from_segments(SEGS)
        self.assertEqual(tl.gaps_between(w, duration=4.0), [{"start": 1.04, "end": 2.5}, {"start": 3.0, "end": 4.0}])
        self.assertEqual(tl.gaps_between(w, duration=3.1), [{"start": 1.04, "end": 2.5}])  # 0.1 s tail < GAP_MIN


class Peaks(unittest.TestCase):
    def test_db_scaled_buckets(self):
        sr, per = 100, 10                          # 10 samples per bucket
        samples = [0.0] * 10 + [1.0] * 10 + [10 ** (-24 / 20)] * 10 + [-0.5] + [0.0] * 9
        p = tl.peaks_from_samples(samples, sr, per)
        self.assertEqual(p[:3], [0.0, 1.0, 0.5])    # silence, 0 dBFS, -24 dB = half of the 48 dB range
        self.assertAlmostEqual(p[3], 0.87, places=2)  # |-0.5| = -6 dB

    def test_words_only_and_cache(self):
        d = tl.words_only(SEGS, 4.0)
        self.assertIsNone(d["peaks"])
        self.assertEqual(len(d["words"]), 4)
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path(tmp) / "c.mp4"; prev.write_bytes(b"x")
            path = tl.cache_path(tmp, "c")
            self.assertEqual(path.name, "c.timeline.json")
            tl.write_cache(path, d, prev)
            self.assertEqual(tl.read_cache(path, prev)["words"][1]["text"], "Kekuatan")
            later = time.time() + 5
            import os; os.utime(prev, (later, later))          # a newer preview invalidates the cache
            self.assertIsNone(tl.read_cache(path, prev))
            path.write_text(json.dumps({**d, "version": 0}))
            self.assertIsNone(tl.read_cache(path))
            self.assertIsNone(tl.read_cache(Path(tmp) / "missing.json"))

    def test_decode_cmd(self):
        self.assertEqual(tl.decode_cmd("/x.mp4")[-3:], ["-f", "f32le", "-"])


if __name__ == "__main__":
    unittest.main()
