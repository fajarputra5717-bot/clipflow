"""Auto Edit E5: shared/style_packs.py + edit_director.plan(mapping=). Run: python3 -m unittest tests.test_style_packs"""
import unittest

from shared import caption_options, edit_director as D, edit_spec as S, style_packs as P


class Packs(unittest.TestCase):
    def test_definitions_are_valid(self):
        presets = {x[0] for x in caption_options.PRESETS}
        for pid, p in P.PACKS.items():
            self.assertIn(p["caption"]["preset"], presets, pid)
            S.normalize_look(p["look"])
            for kind, choices in p["map"].items():
                self.assertIn(kind, D.KINDS + ("loud", "cut"), pid)
                for effect, params in choices:
                    self.assertIn(effect, D.RENDERED_EFFECTS, pid)
                    S.normalize_director({"items": [{"t": 1, "effect": effect, "params": {**D.PARAMS_FOR.get(effect, {}), **params}}]})

    def test_owner_rules(self):
        g, f, d, c = (P.PACKS[k] for k in ("gaming_hype", "funny_meme", "drama_tension", "podcast_clean"))
        self.assertTrue(g["loud"] and g["progress"])
        self.assertFalse(f["loud"] or d["loud"] or c["loud"])
        self.assertEqual([x["min_gap"] for x in (g, f, d, c)], [3, 3, 5, 6])
        self.assertFalse(any(e in ("emoji", "shake") for k in d["map"].values() for e, _ in k))     # drama: no emoji, no shake
        self.assertFalse(any(p.get("sfx") or e in ("emoji", "shake") for k in c["map"].values() for e, p in k))  # podcast
        self.assertEqual(P.pack_for_campaign("ime-roleplay"), "gaming_hype")
        self.assertEqual(P.pack_for_campaign("fandra-octo"), "gaming_hype")
        self.assertEqual(P.pack_for_campaign("motionklip-windah"), "podcast_clean")
        self.assertEqual(P.pack_for_campaign(None), "podcast_clean")
        self.assertEqual(P.resolve({"pack": "funny_meme"}, "ime-roleplay"), ("funny_meme", False))
        self.assertEqual(P.resolve({"pack": "bogus"}, "ime-roleplay"), ("gaming_hype", True))


class Mapping(unittest.TestCase):
    def test_pack_mapping_and_density(self):
        m = [{"t": 2.0, "kind": "laugh", "text": "a"}, {"t": 6.0, "kind": "laugh", "text": "b"},
             {"t": 10.0, "kind": "punchline", "text": "c"}, {"t": 14.0, "kind": "shock", "text": "d"}]
        items = D.plan(duration=30, moments=m, mapping=P.PACKS["funny_meme"]["map"], min_gap=3)
        self.assertEqual([(i["effect"], i["params"]) for i in items],
                         [("emoji", {"emoji": "😂", "sfx": "ding"}), ("emoji", {"emoji": "😭", "sfx": "ding"}),
                          ("freeze", {"hold": 0.6, "sfx": "record_scratch"}), ("slowmo", {"dur": 1.2, "factor": 0.5, })])
        podcast = D.plan(duration=30, moments=m, mapping=P.PACKS["podcast_clean"]["map"], min_gap=6)
        self.assertEqual([(i["t"], i["effect"]) for i in podcast], [(10.0, "punch")])           # laughs/shock unused


if __name__ == "__main__":
    unittest.main()
