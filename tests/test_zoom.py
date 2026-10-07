"""Zoom punch-ins (P4 task 4): edit_spec.zoom + render_steps.zoom_stage. Run: python -m unittest tests.test_zoom"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import render_steps as rs  # noqa: E402
from shared import edit_spec as es  # noqa: E402


class Normalize(unittest.TestCase):
    def test_sorted_dedup_bounds(self):
        v = es.normalize_zoom({"on": True, "intensity": 70, "markers": [9.0, 2.004, 2.0, -1, 40, 5.5]}, 35)
        self.assertEqual(v, {"on": True, "intensity": 70, "markers": [2.0, 5.5, 9.0]})

    def test_default_with_no_markers_is_none(self):
        self.assertIsNone(es.normalize_zoom({"markers": []}, 35))
        self.assertEqual(es.normalize_zoom({"on": False, "markers": []}, 35), {"on": False, "intensity": 50, "markers": []})

    def test_rejects(self):
        for bad in ({"intensity": 101}, {"intensity": "x"}, {"markers": "1"}, {"markers": ["a"]}, {"markers": list(range(41))}, 3):
            with self.assertRaises(ValueError, msg=bad):
                es.normalize_zoom(bad, 100)

    def test_peak_mapping_and_patch(self):
        self.assertEqual((es.zoom_peak(0), es.zoom_peak(50), es.zoom_peak(100)), (1.0, 1.15, 1.3))
        self.assertIn("zoom", es.normalize_patch({"zoom": {"markers": [1]}}, {}, {})[0])


class Stage(unittest.TestCase):
    CAND = {"id": "c", "edit_spec": {"zoom": {"on": True, "intensity": 50, "markers": [2.0, 10.0]}}}

    def test_appends_before_watermark_and_is_one_shot(self):
        filters = ["[0:v]...[stacked];"]
        rs.begin_render(self.CAND, 35)
        last = rs.zoom_stage(filters, "stacked", 1080, 1920, log=lambda m: None)
        self.assertEqual(last, "zoomed")
        self.assertTrue(filters[-1].startswith("[stacked]scale=w='trunc(iw*("))
        self.assertIn("crop=1080:1920", filters[-1])
        self.assertTrue(filters[-1].endswith("[zoomed];"))
        self.assertIn("1+0.15*ld(1)", filters[-1])
        # consumed: the next render_vertical (e.g. a clean plate) gets nothing
        f2 = ["x"]
        self.assertEqual(rs.zoom_stage(f2, "stacked", 1080, 1920, log=lambda m: None), "stacked")
        self.assertEqual(f2, ["x"])

    def test_off_or_no_markers_or_no_context(self):
        for spec in ({"zoom": {"on": False, "markers": [2.0]}}, {"zoom": {"on": True, "markers": []}}, {},
                     {"zoom": {"on": True, "intensity": 0, "markers": [2.0]}}):
            rs.begin_render({"id": "c", "edit_spec": spec}, 35)
            self.assertEqual(rs.zoom_stage([], "stacked", 540, 960, log=lambda m: None), "stacked", spec)
        self.assertEqual(rs.zoom_stage([], "stacked", 540, 960, log=lambda m: None), "stacked")


if __name__ == "__main__":
    unittest.main()
