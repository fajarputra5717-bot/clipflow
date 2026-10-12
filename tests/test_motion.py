"""Auto Edit E2: retention.motion_filter / warp_pieces / warp_graph + edit_director render helpers + posted length.
Run: CAMPAIGNS_DIR=docs/campaigns python3 -m unittest tests.test_motion"""
import os
import unittest

os.environ.setdefault("CAMPAIGNS_DIR", "docs/campaigns")

from shared import edit_director as D  # noqa: E402
from shared import retention as r  # noqa: E402
from shared import rule_checks  # noqa: E402


class Motion(unittest.TestCase):
    def test_none_and_unknown(self):
        self.assertIsNone(r.motion_filter([]))
        self.assertIsNone(r.motion_filter([("emoji", 1.0)]))

    def test_chain_parts(self):
        f = r.motion_filter([("punch", 1.0), ("shake", 3.0), ("whip", 5.0, 4.6), ("flash", 6.5), ("push", 7.0), ("zoom_out", 10.0)],
                            width=540, height=960, duration=12)
        self.assertTrue(f.startswith("scale=w='trunc(iw*(1+("))
        self.assertIn("crop=540:960:'clip(", f)
        self.assertIn("sin(2*PI*13*(t-3))", f)                    # shake x
        self.assertIn("avgblur=sizeX=31:sizeY=1:enable='between(t,4.45,4.6)+between(t,5,5.15)'", f)   # whip both sides of the cut
        self.assertIn("eq=brightness='0.55*(1-(t-6.5)/0.2)*between(t,6.5,6.7)':eval=frame", f)
        self.assertIn("0.08*", f)                                  # push peak
        self.assertIn("0.18*(1-", f)                               # zoom-out starts in, pulls back

    def test_punch_matches_old_zoom(self):
        self.assertIn(r.zoom_expr(r.plan_zoom_windows([2.0], 10), peak=1.15), r.motion_filter([("punch", 2.0)], duration=10))
        self.assertNotIn("1+0.15", r.motion_filter([("punch", 2.0)], duration=10, punch_peak=1.0) or "")


class Warps(unittest.TestCase):
    def test_pieces_and_length(self):
        p = r.warp_pieces([(0, 4), (5, 10)], [("freeze", 2.0, 0.6), ("slowmo", 6.0, 1.2, 0.5)])
        self.assertEqual(p, [[0.0, 2.0, 1.0, 0.6], [2.0, 4.0, 1.0, 0.0], [5.0, 6.0, 1.0, 0.0], [6.0, 7.2, 0.5, 0.0], [7.2, 10.0, 1.0, 0.0]])
        self.assertAlmostEqual(r.pieces_output_seconds(p), 10.8)

    def test_outside_and_edges(self):
        self.assertEqual(r.warp_pieces([(0, 4)], [("freeze", 4.5, 0.6)]), [[0.0, 4.0, 1.0, 0.0]])          # cut away: ignored
        self.assertEqual(r.warp_pieces([(0, 4)], [("slowmo", 3.5, 1.2, 0.5)]), [[0.0, 3.5, 1.0, 0.0], [3.5, 4.0, 0.5, 0.0]])  # clipped
        self.assertEqual(r.warp_pieces([(0, 4)], [("freeze", 0.0, 0.5)])[0], [0.0, 0.04, 1.0, 0.5])         # at the start

    def test_graph(self):
        keep = [(0.0, 4.0), (5.0, 10.0)]
        g = r.warp_graph(keep, r.warp_pieces(keep, [("freeze", 2.0, 0.6), ("slowmo", 6.0, 1.2, 0.5)]), duration=10)
        self.assertIn("tpad=stop_mode=clone:stop_duration=0.6", g)
        self.assertIn("apad=pad_dur=0.6", g)
        self.assertIn("setpts=(PTS-STARTPTS)/0.5", g)
        self.assertIn("atempo=0.5", g)
        self.assertIn("concat=n=5:v=1:a=0[vtrim]", g)
        self.assertIn("acrossfade=d=0.04", g)                      # across the cut only
        self.assertEqual(g.count("acrossfade"), 1)


class Director(unittest.TestCase):
    plan = {"items": [{"t": 2, "effect": "freeze", "on": True}, {"t": 6, "effect": "slowmo", "on": True, "params": {"factor": 0.75}},
                      {"t": 5, "effect": "whip", "on": True}, {"t": 1, "effect": "shake", "on": False}, {"t": 8, "effect": "emoji", "on": True}]}

    def test_events_and_warps(self):
        self.assertEqual(D.motion_events(self.plan, [[4, 5]]), [("whip", 5.0, 4.0)])
        self.assertEqual(D.motion_events(self.plan), [("whip", 5.0, 5.0)])
        self.assertEqual(D.warps(self.plan), [("freeze", 2.0, 0.6), ("slowmo", 6.0, 1.2, 0.75)])
        self.assertIn("freeze", D.RENDERED_EFFECTS)
        self.assertNotIn("emoji", D.RENDERED_EFFECTS)

    def test_posted_length_counts_time_effects(self):
        c = {"start_time": 0, "end_time": 10, "edit_spec": {"cuts": {"trim": None, "removed": [[4, 5]]}, "director": self.plan}}
        self.assertAlmostEqual(rule_checks._duration(c), 9 + 0.6 + 1.2 * (1 / 0.75 - 1), places=2)
        self.assertAlmostEqual(rule_checks._duration({"start_time": 0, "end_time": 10, "edit_spec": None}), 10)
        self.assertEqual(D.keep_of({"cuts": {"trim": [1, 9], "removed": [[3, 4]]}}, 10), [(1.0, 3.0), (4.0, 9.0)])


if __name__ == "__main__":
    unittest.main()
