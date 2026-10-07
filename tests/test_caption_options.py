"""Task 7a: shared/caption_options.py (the Editor's caption catalogue) must match make_ass() in worker.py
and main.py's accepted names. Same rules as scripts/check_caption_mirror.py.
Run: python -m unittest tests.test_caption_options"""

import ast
import re
import unittest
from pathlib import Path

from shared import caption_options as co
from shared import edit_spec as es
from shared import fonts

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "worker/worker.py").read_text()
MAIN = (ROOT / "backend/app/main.py").read_text()


def hexnorm(c):
    c = c.strip().lower()
    return "#" + "".join(ch * 2 for ch in c[1:]) if re.fullmatch(r"#[0-9a-f]{3}", c) else c


class MirrorsMakeAss(unittest.TestCase):
    ass = ast.literal_eval(re.search(r"\n    styles = (\{.*?\n    \})\n", WORKER, re.S).group(1))
    anims = set(re.findall(r'^\s{4}"([a-z_]+)":', re.search(r"\nANIMATIONS = \{(.*?)\n\}", WORKER, re.S).group(1), re.M))

    def test_styles(self):
        self.assertEqual(set(co.STYLE_PREVIEW), set(self.ass))
        self.assertEqual(set(co.STYLE_LABELS), set(self.ass))
        for name, a in self.ass.items():
            p = co.STYLE_PREVIEW[name]
            with self.subTest(style=name):
                self.assertEqual(hexnorm(p["resting"]), hexnorm(a["resting"]))
                self.assertEqual(hexnorm(p["highlight"]), hexnorm(a["highlight"]))
                self.assertEqual(float(p["outline"]), a["outline"] / 2)
                self.assertEqual(p["shadow"], a["shadow"] > 0)
                self.assertEqual(p["box"], a["border_style"] == 3)
                self.assertEqual(float(p["sizeMult"]), float(a["size_mult"]))

    def test_animations_and_presets(self):
        self.assertEqual({a for a, _, _ in co.ANIMATIONS}, self.anims)
        for _, _, st, an in co.PRESETS:
            self.assertIn(st, self.ass)
            self.assertIn(an, self.anims)

    def test_main_accepts_the_same_names(self):
        presets = re.search(r"SUBTITLE_STYLE_PRESETS = \{(.*?)\}", MAIN, re.S).group(1)
        self.assertEqual(set(re.findall(r'"([a-z]+)"', presets)), set(co.STYLE_PREVIEW))
        sizes = re.search(r"subtitle_size: int = Field\(\s*default=\d+,\s*ge=(\d+),\s*le=(\d+)", MAIN).groups()
        self.assertEqual(tuple(int(x) for x in sizes), co.SIZE_RANGE)

    def test_options_payload(self):
        o = co.options()
        self.assertEqual(o["fonts"], list(fonts.CAPTION_FONTS))
        self.assertEqual([k["color"] for k in o["keyword_colors"]], es.KEYWORD_PALETTE)
        self.assertEqual(o["caption_y_range"], list(es.CAPTION_Y_RANGE))
        self.assertEqual(co.auto_keyword_color("hormozi"), "#30D158")   # yellow highlight → next palette colour
        self.assertEqual(co.auto_keyword_color("outline"), "#30D158")
        self.assertEqual(co.auto_keyword_color("neon"), "#FFD60A")


if __name__ == "__main__":
    unittest.main()
