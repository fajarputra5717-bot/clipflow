"""P4 task 5: progress bar ASS + compression + edit_spec progress/audio. Run: python -m unittest tests.test_effects"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import render_steps as rs  # noqa: E402
from shared import edit_spec as es  # noqa: E402


class Spec(unittest.TestCase):
    def test_progress(self):
        self.assertEqual(es.normalize_progress({"on": True, "color": "#ff453a"}), {"on": True, "color": "#FF453A"})
        self.assertIsNone(es.normalize_progress({"on": False}))
        with self.assertRaises(ValueError):
            es.normalize_progress({"on": True, "color": "red"})
        self.assertIsNone(es.progress_of({"progress": {"on": False, "color": "#FFFFFF"}}))

    def test_audio(self):
        self.assertEqual(es.normalize_audio({"compress": True}), {"compress": True, "silence_trim": False, "silence_ranges": []})
        self.assertIsNone(es.normalize_audio({}))
        self.assertEqual(es.normalize_audio({"silence_trim": True, "silence_ranges": [[1, 1.5], [3, 2]]})["silence_ranges"], [[1.0, 1.5]])
        with self.assertRaises(ValueError):
            es.normalize_audio({"silence_ranges": [["a", 1]]})
        # QA 2e3d583 Low: clamped to the clip like cuts
        clamped = es.normalize_audio({"silence_trim": True, "silence_ranges": [[20, 9999], [-1, 2], [40, 50]]}, 35)
        self.assertEqual(clamped["silence_ranges"], [[0.0, 2.0], [20.0, 35.0]])
        self.assertEqual(set(es.normalize_patch({"progress": {"on": True}, "audio": {"compress": True}}, {}, {})[0]), {"progress", "audio"})


class ProgressBar(unittest.TestCase):
    def test_continuous_through_cuts(self):
        ev = rs.progress_events("#FF453A", 1080, 1920, [(0.0, 2.0), (3.0, 5.0)], 35)
        self.assertEqual(len(ev), 4)                                  # track + fill per kept segment
        fills = [e for e in ev if e.startswith("Dialogue: 31")]
        self.assertIn("0:00:00.00,0:00:02.00", fills[0])
        self.assertIn("\\fscx0.000\\t(0,2000,\\fscx50.000)", fills[0])   # 0 → 50 % over the first 2 s of 4 s output
        self.assertIn("0:00:03.00,0:00:05.00", fills[1])
        self.assertIn("\\fscx50.000\\t(0,2000,\\fscx100.000)", fills[1])
        self.assertIn("\\1c&H3A45FF&", fills[0])                        # #FF453A as BGR
        self.assertIn("m 0 0 l 1080 0 1080 12 0 12", ev[0])            # 0.6 % of 1920 = 12 px

    def test_added_to_ass_or_own_file(self):
        cand = {"id": "c1", "edit_spec": {"progress": {"on": True, "color": "#FFFFFF"}}}
        with tempfile.TemporaryDirectory() as d:
            out = rs.add_title_card(None, cand, size=(540, 960), clip_duration=10, out_dir=d, log=lambda m: None)
            body = Path(out).read_text(encoding="utf-8")
            self.assertEqual(Path(out).name, "c1.title.ass")
            self.assertIn("Style: Progress,", body)
            self.assertEqual(len(re.findall(r"^Dialogue: 3[01],0:00:00.00,0:00:10.00,Progress", body, re.M)), 2)
            cand["edit_spec"]["hook_title"] = {"on": True, "text": "Hi", "duration": 2}
            ass = Path(d) / "c2.ass"
            ass.write_text("[Script Info]\n\n[V4+ Styles]\nFormat: Name\nStyle: Default,X\n\n[Events]\nFormat: Layer\n", encoding="utf-8")
            out2 = rs.add_title_card(str(ass), {**cand, "id": "c2"}, size=(540, 960), clip_duration=10, log=lambda m: None)
            b2 = Path(out2).read_text(encoding="utf-8")
            self.assertTrue("Style: HookCard," in b2 and "Style: Progress," in b2)
            self.assertLess(b2.index("Style: Progress"), b2.index("[Events]"))
        self.assertIsNone(rs.add_title_card(None, {"id": "c", "edit_spec": {}}, size=(1, 1), clip_duration=1))


class Compression(unittest.TestCase):
    def test_compress_only_copies_video(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.mp4"; f.write_bytes(b"x")
            run = lambda argv, timeout=None: (calls.append(argv), Path(argv[-1]).write_bytes(b"y"))
            out = rs.apply_cuts(f, {"id": "c", "edit_spec": {"audio": {"compress": True}}}, 10, preset="veryfast", crf=20, run=run, log=lambda m: None)
        self.assertIsNone(out)
        self.assertIn("-c:v", calls[0]); self.assertEqual(calls[0][calls[0].index("-c:v") + 1], "copy")
        self.assertIn(rs.COMPRESSOR, calls[0])

    def test_cuts_plus_compress_in_one_pass(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.mp4"; f.write_bytes(b"x")
            run = lambda argv, timeout=None: (calls.append(argv), Path(argv[-1]).write_bytes(b"y"))
            spec = {"cuts": {"trim": None, "removed": [[2.0, 3.0]]}, "audio": {"compress": True}}
            rs.apply_cuts(f, {"id": "c", "edit_spec": spec}, 10, preset="veryfast", crf=20, run=run, log=lambda m: None)
        g = calls[0][calls[0].index("-filter_complex") + 1]
        self.assertIn(f";[atrim]{rs.COMPRESSOR}[acomp]", g)
        self.assertEqual(calls[0][calls[0].index("[vtrim]") + 2], "[acomp]")


if __name__ == "__main__":
    unittest.main()
