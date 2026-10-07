"""Hook title card (P4 task 1): edit_spec validation + render_steps ASS. Run: python -m unittest tests.test_render_steps"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import render_steps as rs  # noqa: E402
from shared import edit_spec as es  # noqa: E402

CAND = {"id": "cand-1", "ai_title": "Kekuatan Sihir? Pemain Ini Dicurigai 🔥", "manual_title": None, "title": None,
        "edit_spec": {"hook_title": {"on": True, "text": "", "duration": 2.5}}}


class Spec(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(es.normalize_hook_title({"on": True, "text": "  Hi   there ", "duration": 3}),
                         {"on": True, "text": "Hi there", "duration": 3.0})
        self.assertEqual(es.normalize_hook_title({})["duration"], 2.5)
        self.assertIsNone(es.normalize_hook_title(None))
        for bad in ({"duration": 4}, {"text": "x" * 81}, "on", {"duration": "soon"}):
            with self.assertRaises(ValueError):
                es.normalize_hook_title(bad)

    def test_patch_accepts_hook_title(self):
        merge, remove = es.normalize_patch({"hook_title": {"on": False}}, {}, {})
        self.assertEqual(merge["hook_title"]["on"], False)
        self.assertEqual(es.normalize_patch({"hook_title": None}, {}, {}), ({}, ["hook_title"]))


class Card(unittest.TestCase):
    def test_text_defaults_to_title_and_strips_emoji(self):
        self.assertEqual(rs.card_text(CAND), "Kekuatan Sihir? Pemain Ini Dicurigai")
        self.assertEqual(rs.card_text({**CAND, "edit_spec": {"hook_title": {"on": True, "text": "Own text", "duration": 2}}}), "Own text")
        self.assertIsNone(rs.card_text({**CAND, "edit_spec": {"hook_title": {"on": False}}}))
        self.assertIsNone(rs.card_text({**CAND, "edit_spec": None}))

    def test_layout_scales_with_canvas_and_clears_watermark(self):
        wm = {"x": 380, "y": 400, "w": 320, "h": 80}
        f = rs.card_layout("A hook title", 1080, 1920, wm)
        p = rs.card_layout("A hook title", 540, 960, {k: v // 2 for k, v in wm.items()})
        self.assertGreaterEqual(f["top"], wm["y"] + wm["h"])              # never over the watermark
        self.assertAlmostEqual(f["top"] / 1920, p["top"] / 960, delta=0.003)  # preview == final, scaled
        self.assertAlmostEqual(f["w"] / 1080, p["w"] / 540, delta=0.02)
        self.assertGreaterEqual(rs.card_layout("x", 1080, 1920)["top"], 0.16 * 1920)  # below top UI
        self.assertLessEqual(len(rs.wrap("word " * 60, 58, 700)), 3)

    def test_append_to_existing_ass(self):
        with tempfile.TemporaryDirectory() as d:
            ass = Path(d) / "c.ass"
            ass.write_text("[Script Info]\nPlayResX: 1080\n\n[V4+ Styles]\nFormat: Name,Fontname\nStyle: Default,X\n\n"
                           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
                           "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,HELLO\n", encoding="utf-8")
            out = rs.add_title_card(str(ass), CAND, size=(1080, 1920), clip_duration=34, log=lambda m: None)
            body = Path(out).read_text(encoding="utf-8")
            self.assertEqual(out, str(ass))
            self.assertIn("Style: HookCard,Montserrat ExtraBold,", body)
            self.assertLess(body.index("Style: HookCard"), body.index("[Events]"))
            self.assertIn("HELLO", body)                                   # captions untouched
            cards = re.findall(r"Dialogue: 2[012],0:00:00\.00,0:00:02\.50,HookCard", body)
            self.assertEqual(len(cards), 3)                                # shadow, card, text

    def test_captions_off_writes_title_only_ass_named_by_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            out = rs.add_title_card(None, CAND, size=(540, 960), clip_duration=1.8, out_dir=d, log=lambda m: None)
            self.assertEqual(Path(out).name, "cand-1.title.ass")
            body = Path(out).read_text(encoding="utf-8")
            self.assertIn("PlayResY: 960", body)
            self.assertIn("0:00:00.00,0:00:01.80,HookCard", body)            # capped at the clip length

    def test_off_or_failure_returns_input(self):
        self.assertEqual(rs.add_title_card("x.ass", {**CAND, "edit_spec": {}}, size=(1, 1), clip_duration=1), "x.ass")
        self.assertEqual(rs.add_title_card(None, {"edit_spec": {"hook_title": {"on": True, "text": "t"}}},
                                           size=(1080, 1920), clip_duration=3, log=lambda m: None), None)  # no id → skipped


if __name__ == "__main__":
    unittest.main()
