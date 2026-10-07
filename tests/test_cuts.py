"""P4 task 3: edit_spec.cuts validation + render_steps cut plan / card window. Run: python -m unittest tests.test_cuts"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import render_steps as rs  # noqa: E402
from shared import edit_spec as es  # noqa: E402
from shared import timeline as tl  # noqa: E402


class NormalizeCuts(unittest.TestCase):
    def test_merge_clamp_round(self):
        v = es.normalize_cuts({"trim": [1.0, 30.0], "removed": [[5.5, 6.0], [0.2, 2.0], [5.9, 7.0001], [10, 10.01]]}, 35)
        self.assertEqual(v, {"trim": [1.0, 30.0], "removed": [[1.0, 2.0], [5.5, 7.0]]})

    def test_whole_clip_trim_and_empty_mean_none(self):
        self.assertIsNone(es.normalize_cuts({"trim": [0, 35], "removed": []}, 35))
        self.assertIsNone(es.normalize_cuts({}, 35))
        self.assertEqual(es.normalize_cuts({"trim": [0, 35], "removed": [[1, 2]]}, 35), {"trim": None, "removed": [[1.0, 2.0]]})

    def test_rejects(self):
        for bad in ({"trim": [3, 3.5]}, {"removed": [[0, 34.5]]}, {"trim": "x"}, {"removed": [["a", 1]]}, [1, 2],
                    {"removed": [[0, 1]] * 401}):
            with self.assertRaises(ValueError, msg=bad):
                es.normalize_cuts(bad, 35)
        self.assertIsNone(es.normalize_cuts(None))

    def test_patch_route_accepts_cuts(self):
        merge, _ = es.normalize_patch({"cuts": {"removed": [[1, 2]]}}, {}, {})
        self.assertEqual(merge["cuts"]["removed"], [[1.0, 2.0]])


class Plan(unittest.TestCase):
    def cand(self, cuts):
        return {"id": "c", "edit_spec": {"cuts": cuts}}

    def test_keep_snapped_to_frames(self):
        keep = rs.cut_plan(self.cand({"trim": [0.51, 20.0], "removed": [[5.013, 6.517]]}), 35, fps=30)
        self.assertEqual(len(keep), 2)
        for a, b in keep:
            self.assertAlmostEqual(a * 30, round(a * 30), places=6)
            self.assertAlmostEqual(b * 30, round(b * 30), places=6)
        self.assertAlmostEqual(keep[0][0], 0.5, places=6)
        self.assertLessEqual(keep[-1][1], 20.0)

    def test_no_cuts_is_none(self):
        self.assertIsNone(rs.cut_plan({"id": "c", "edit_spec": {}}, 35))
        self.assertIsNone(rs.cut_plan({"id": "c", "edit_spec": None}, 35))

    def test_card_window_fills_output_seconds(self):
        self.assertEqual(rs.card_window(2.5, None), (0.0, 2.5))
        self.assertEqual(rs.card_window(2.5, [(1.0, 2.0), (3.0, 10.0)]), (1.0, 4.5))   # 1 s + 1.5 s
        self.assertEqual(rs.card_window(2.5, [(1.0, 2.0)]), (1.0, 2.0))               # output shorter than the card

    def test_card_starts_at_trim(self):
        c = {"id": "c", "ai_title": "Title", "edit_spec": {"hook_title": {"on": True, "text": "", "duration": 2.0},
                                                           "cuts": {"trim": [3.0, 30.0], "removed": []}}}
        out = rs.add_title_card(None, c, size=(540, 960), clip_duration=35, out_dir="/tmp", log=lambda m: None)
        body = Path(out).read_text(encoding="utf-8")
        self.assertIn("Dialogue: 22,0:00:03.00,0:00:05.00,HookCard", body)


class BurnSegments(unittest.TestCase):
    SEGS = [{"start": 10.0, "end": 12.0, "text": "FINALITY GAS AJA", "words": [
                {"word": "FINALITY", "start": 10.0, "end": 10.8}, {"word": "GAS", "start": 10.9, "end": 11.3},
                {"word": "AJA", "start": 11.3, "end": 11.7}]},
            {"start": 12.0, "end": 14.0, "text": "GOALIN AJA AMAN", "words": [
                {"word": "GOALIN", "start": 12.0, "end": 12.5}, {"word": "AJA", "start": 12.5, "end": 12.9},
                {"word": "AMAN", "start": 13.0, "end": 13.6}]},
            {"start": 20.0, "end": 21.0, "text": "GONE", "words": [{"word": "GONE", "start": 20.0, "end": 21.0}]}]

    def cand(self, cuts):
        return {"id": "c", "edit_spec": {"cuts": cuts}}

    def test_cut_words_leave_the_line_and_kept_words_keep_source_times(self):
        out = rs.burn_segments(self.SEGS, self.cand({"trim": None, "removed": [[10.9, 12.9], [19.9, 21.1]]}), 35)
        self.assertEqual([s["text"] for s in out], ["FINALITY", "AMAN"])   # "GAS AJA" + "GOALIN AJA" gone, "GONE" line dropped
        self.assertEqual((out[0]["start"], out[0]["end"]), (10.0, 10.8))
        self.assertEqual((out[1]["start"], out[1]["end"], out[1]["words"][0]["start"]), (13.0, 14.0, 13.0))

    def test_trim_and_half_rule(self):
        out = rs.burn_segments(self.SEGS, self.cand({"trim": [10.5, 30.0], "removed": []}), 35)
        self.assertEqual(out[0]["text"], "GAS AJA")                        # FINALITY 10.0–10.8: 5/8 outside trim
        self.assertEqual(len(out), 3)

    def test_no_cuts_returns_input(self):
        self.assertIs(rs.burn_segments(self.SEGS, {"id": "c", "edit_spec": {}}, 35), self.SEGS)


class TimelineKeep(unittest.TestCase):
    def test_words_only_has_keep_none_and_version(self):
        d = tl.words_only([], 10)
        self.assertEqual((d["version"], d["keep"]), (2, None))
        self.assertIn("-ss", tl.decode_cmd("/x.mp4", start=26.0, duration=35.0))


if __name__ == "__main__":
    unittest.main()
