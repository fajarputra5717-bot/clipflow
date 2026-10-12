"""Auto Edit E1: shared/edit_director.py + edit_spec.normalize_director. Run: python3 -m unittest tests.test_edit_director"""
import unittest

from shared import edit_director as D
from shared import edit_spec as S


def words(*pairs):
    return [{"text": w, "start": t, "end": t + 0.3} for t, w in pairs]


class Prompt(unittest.TestCase):
    def test_lines_and_frames(self):
        w = words((0.0, "eh"), (0.5, "lihat"), (3.2, "BOOM"), (3.6, "haha"))
        self.assertEqual(D.transcript_lines(w), ["[0.0] eh lihat", "[3.2] BOOM haha"])
        p = D.moments_prompt(w, 10, frame_times=[1.0, 5.0])
        self.assertIn("[3.2] BOOM haha", p)
        self.assertIn("1.0 s, 5.0 s", p)
        self.assertNotIn("Frames", D.moments_prompt(w, 10))

    def test_parse_drops_bad_rows(self):
        data = {"moments": [{"t": 2.345, "kind": "punchline", "text": "x"}, {"t": 99, "kind": "hook", "text": ""},
                            {"t": "a", "kind": "hook"}, {"t": 1, "kind": "dance"}, {"t": -1, "kind": "laugh"}]}
        self.assertEqual(D.parse_moments(data, 10), [{"t": 2.35, "kind": "punchline", "text": "x"}])
        self.assertEqual(D.parse_moments(None, 10), [])


class Signals(unittest.TestCase):
    def test_loudness_peaks(self):
        rate = 10
        peaks = [0.1] * 100
        peaks[20] = 1.0
        peaks[22] = 0.95      # same window as 20: not a second peak
        peaks[70] = 0.9
        peaks[50] = 0.5       # below 85 % of max
        self.assertEqual(D.loudness_peaks(peaks, rate), [2.0, 7.0])
        self.assertEqual(D.loudness_peaks(None, rate), [])
        self.assertEqual(D.loudness_peaks([0, 0], rate), [])

    def test_cut_points(self):
        self.assertEqual(D.cut_points([[4.0, 5.0], [1.5, 2.0]]), [2.0, 5.0])   # first kept moment after each cut


class Restraint(unittest.TestCase):
    def test_gap_priority_card_cuts_end(self):
        items = D.plan(duration=20,
                       moments=[{"t": 1.0, "kind": "hook", "text": "a"},        # under the title card
                                {"t": 6.0, "kind": "punchline", "text": "b"},
                                {"t": 12.0, "kind": "laugh", "text": "c"},       # inside a cut
                                {"t": 19.8, "kind": "shock", "text": "d"}],      # too close to the end
                       loud=[7.0, 15.0], cuts=[], card_seconds=2.5, removed=[[11.0, 13.0]])
        self.assertEqual([(i["t"], i["effect"], i["source"]) for i in items],
                         [(6.0, "punch", "transcript"), (15.0, "shake", "audio")])
        self.assertTrue(all(i["on"] for i in items))
        for a, b in zip(items, items[1:]):
            self.assertGreaterEqual(b["t"] - a["t"], D.MIN_GAP)

    def test_vision_reaction_and_trim(self):
        items = D.plan(duration=30, moments=[{"t": 4.0, "kind": "reaction", "text": "face"},
                                             {"t": 25.0, "kind": "laugh", "text": "lol"}], trim=[2.0, 20.0])
        self.assertEqual([(i["effect"], i["source"]) for i in items], [("punch", "vision")])

    def test_emoji_params_and_punch_markers(self):
        items = D.plan(duration=10, moments=[{"t": 5.0, "kind": "laugh", "text": "x"}, {"t": 1.0, "kind": "hook", "text": "y"}])
        self.assertEqual(items[1]["params"], {"emoji": "😂"})
        items[0]["on"] = True
        self.assertEqual(D.punch_markers({"items": items}), [1.0])
        items[0]["on"] = False
        self.assertEqual(D.punch_markers({"items": items}), [])

    def test_frames(self):
        self.assertEqual(D.frame_times(12, count=6), [1.0, 3.0, 5.0, 7.0, 9.0, 11.0])
        self.assertEqual(D.frame_times(12, count=6, removed=[[4.5, 7.5]]), [1.0, 3.0, 9.0, 11.0])
        cmd = D.frame_cmd("/s.mp4", 100.0, 2.5, "/p/x.frame-0.jpg")
        self.assertEqual(cmd[cmd.index("-ss") + 1], "102.500")
        self.assertIn("scale=320:-2", cmd)


class OutputTimeAndManualMarkers(unittest.TestCase):
    """Lane C a156a53 Medium: spacing in OUTPUT seconds after cuts, and the user's zoom markers count."""
    def test_manual_markers_are_taken(self):
        m = [{"t": 4.6, "kind": "punchline", "text": "a"}, {"t": 27.2, "kind": "shock", "text": "b"},
             {"t": 15.0, "kind": "laugh", "text": "c"}]
        items = D.plan(duration=30, moments=m, taken=[5.0, 26.0])
        self.assertEqual([i["t"] for i in items], [15.0])

    def test_spacing_measured_after_cuts(self):
        # 4 s apart in source, but 3 s of it is cut: 1 s apart in the output -> only the first survives
        m = [{"t": 2.0, "kind": "punchline", "text": "a"}, {"t": 6.0, "kind": "shock", "text": "b"}]
        keep = [[0.0, 3.0], [6.0, 20.0]]
        items = D.plan(duration=20, moments=m, removed=[[3.0, 6.0]], keep=keep)
        self.assertEqual([i["t"] for i in items], [2.0])
        # the hook card covers the first 2.5 OUTPUT seconds: source 7.0 is output 4.0, allowed; 2.0 is not
        items = D.plan(duration=20, moments=[{"t": 2.0, "kind": "hook", "text": "a"}, {"t": 7.0, "kind": "shock", "text": "b"}],
                       removed=[[3.0, 6.0]], keep=keep, card_seconds=2.5)
        self.assertEqual([i["t"] for i in items], [7.0])

    def test_cut_seam_is_kept(self):
        items = D.plan(duration=20, cuts=D.cut_points([[8.0, 10.0]]), removed=[[8.0, 10.0]], keep=[[0, 8], [10, 20]])
        self.assertEqual([(i["t"], i["effect"]) for i in items], [(10.0, "whip")])


class Normalize(unittest.TestCase):
    def test_round_trip_and_rules(self):
        v = S.normalize_director({"provider": "gemini", "vision": 1, "items": [
            {"t": 5.123, "effect": "punch", "reason": "r", "source": "transcript", "on": False},
            {"t": 2, "effect": "whip", "source": "weird"},
            {"t": 50, "effect": "punch"}]}, 10)
        self.assertEqual([(i["t"], i["effect"], i["source"], i["on"]) for i in v["items"]],
                         [(2.0, "whip", "user", True), (5.12, "punch", "transcript", False)])
        self.assertTrue(v["vision"])
        self.assertIsNone(S.normalize_director(None))
        for bad in ("x", {"items": "x"}, {"items": [{"t": 1, "effect": "Bad Effect"}]},
                    {"items": [{"t": "a", "effect": "punch"}]}, {"items": [{"t": 1, "effect": "punch", "params": {"p": "x" * 400}}]}):
            with self.assertRaises(ValueError):
                S.normalize_director(bad, 10)


if __name__ == "__main__":
    unittest.main()
