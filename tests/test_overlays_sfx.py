"""Auto Edit E3: emoji pops + SFX (retention.emoji_filters / sfx_mix_cmd, edit_director helpers, bundled assets).
Run: python3 -m unittest tests.test_overlays_sfx"""
import unittest
from pathlib import Path

from shared import edit_director as D
from shared import retention as r

ASSETS = Path(__file__).resolve().parents[1] / "worker" / "assets"


class Assets(unittest.TestCase):
    def test_every_emoji_and_sfx_is_bundled_and_licensed(self):
        lic = (ASSETS / "LICENSES.md").read_text()
        for ch, code in D.EMOJI.items():
            self.assertTrue((ASSETS / "emoji" / f"{code}.png").is_file(), ch)
        for name in D.SFX:
            self.assertTrue((ASSETS / "sfx" / f"{name}.wav").is_file(), name)
            self.assertIn(f"{name}.wav", lic)
        self.assertIn("Noto Emoji", lic); self.assertIn("Apache License 2.0", lic); self.assertNotIn("Twemoji", lic)
        self.assertIn("watermark.png", lic)


class Emoji(unittest.TestCase):
    def test_events_alternate_sides(self):
        d = {"items": [{"t": 2, "effect": "emoji", "on": True, "params": {"emoji": "💀"}},
                       {"t": 6, "effect": "emoji", "on": True}, {"t": 9, "effect": "emoji", "on": False},
                       {"t": 12, "effect": "emoji", "on": True, "params": {"emoji": "🦄"}}]}       # not bundled: skipped
        self.assertEqual(D.emoji_events(d), [(2.0, "1f480", "right"), (6.0, "1f602", "left")])

    def test_filters(self):
        chunks, last = r.emoji_filters("base", [(2.0, "1f480", "right")], "/app/assets/emoji", width=540, height=960)
        g = "".join(chunks)
        self.assertEqual(last, "emo0")
        self.assertIn("movie='/app/assets/emoji/1f480.png'", g)
        self.assertIn("trim=start=2:end=3.4", g)
        self.assertIn("fade=t=out:st=3.2:d=0.2:alpha=1", g)
        self.assertIn("[base][em0]overlay=x='0.72*W-w/2':y='0.42*H-h/2':eof_action=pass", g)


class Sfx(unittest.TestCase):
    def test_events_follow_cuts_and_time_effects(self):
        d = {"items": [{"t": 2, "effect": "freeze", "on": True, "params": {"sfx": "record_scratch"}},
                       {"t": 4.5, "effect": "punch", "on": True, "params": {"sfx": "boom"}},       # inside the cut: dropped
                       {"t": 6, "effect": "whip", "on": True, "params": {"sfx": "whoosh"}},
                       {"t": 8, "effect": "shake", "on": True, "params": {"sfx": "laugh"}}]}      # not bundled: dropped
        keep = [(0.0, 4.0), (5.0, 10.0)]
        pieces = r.warp_pieces(keep, D.warps(d))
        self.assertEqual(D.sfx_events(d, keep, pieces), [(2.0, "record_scratch"), (5.6, "whoosh")])   # freeze adds 0.6
        self.assertEqual(D.to_output(4.5, keep), None)
        self.assertEqual(D.to_output(6.0, keep), 5.0)

    def test_mix_cmd(self):
        self.assertIsNone(r.sfx_mix_cmd("/a.mp4", "/b.mp4", [], "/s"))
        a = r.sfx_mix_cmd("/a.mp4", "/b.mp4", [(1.25, "whoosh"), (3.0, "boom")], "/s")
        g = a[a.index("-filter_complex") + 1]
        self.assertIn("/s/whoosh.wav", a)
        self.assertIn("adelay=1250|1250", g)
        self.assertIn("sidechaincompress", g)               # ducked under the speech
        self.assertIn("amix=inputs=2:normalize=0:duration=first[aout]", g)
        self.assertEqual(a[a.index("-c:v") + 1], "copy")


if __name__ == "__main__":
    unittest.main()


class Look(unittest.TestCase):
    """Auto Edit E4: look_filter + normalize_look."""
    def test_filter(self):
        self.assertIsNone(r.look_filter(None))
        self.assertIsNone(r.look_filter({"preset": "none"}))
        self.assertEqual(r.look_filter({"preset": "moody", "vignette": True, "grain": True}),
                         r.LOOKS["moody"] + ",vignette=angle=PI/5,noise=alls=6:allf=t")

    def test_normalize(self):
        from shared import edit_spec as S
        self.assertIsNone(S.normalize_look({"preset": "none"}))
        self.assertEqual(S.normalize_look({"preset": "warm", "grain": 1}), {"preset": "warm", "vignette": False, "grain": True})
        with self.assertRaises(ValueError):
            S.normalize_look({"preset": "sepia"})
