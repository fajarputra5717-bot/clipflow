"""shared/sfx_library.py (217): `python3 -m unittest tests.test_sfx_library`."""
import unittest

from shared import edit_director, retention, style_packs
from shared import sfx_library as lib

CC0 = "http://creativecommons.org/publicdomain/zero/1.0/"


def fs(i, rating=4.0, n=10, dl=100, dur=1.5, lic=CC0, preview=True):
    return {"id": i, "name": f"laugh {i}.wav", "username": "someone", "license": lic, "duration": dur,
            "avg_rating": rating, "num_ratings": n, "num_downloads": dl, "url": f"https://freesound.org/s/{i}/",
            "previews": {"preview-hq-mp3": f"https://cdn.freesound.org/previews/{i // 1000}/{i}_77-hq.mp3"} if preview else {}}


class CategoriesTest(unittest.TestCase):
    def test_categories_cover_the_mixer(self):
        self.assertEqual(set(lib.CATEGORIES), set(edit_director.SFX))
        self.assertEqual(set(lib.BUNDLED) | set(lib.FALLBACK), set(edit_director.SFX))

    def test_resolve(self):
        p = lib.resolve_paths({}, "/app/assets/sfx/")
        self.assertEqual(p["laugh"], "/app/assets/sfx/ding.wav")       # no laugh recording → ding
        self.assertEqual(p["boom"], "/app/assets/sfx/boom.wav")
        p = lib.resolve_paths({"laugh": "/data/sfx/u/a.wav", "boom": "/data/sfx/u/b.wav", "junk": "/x"}, "/s")
        self.assertEqual((p["laugh"], p["boom"], p["ding"]), ("/data/sfx/u/a.wav", "/data/sfx/u/b.wav", "/s/ding.wav"))
        self.assertNotIn("junk", p)

    def test_funny_meme_laugh_uses_the_laugh_category(self):
        self.assertIn("Funny / Meme", lib.used_by("laugh"))
        self.assertIn("Gaming Hype", lib.used_by("boom"))
        laugh = style_packs.PACKS["funny_meme"]["map"]["laugh"]
        self.assertTrue(all(params["sfx"] == "laugh" for _e, params in laugh))

    def test_mixer_takes_the_paths(self):
        argv = retention.sfx_mix_cmd("in.mp4", "out.mp4", [(1.0, "laugh"), (2.0, "boom")], "/s",
                                     paths=lib.resolve_paths({"laugh": "/data/sfx/u/a.wav"}, "/s"))
        self.assertIn("/data/sfx/u/a.wav", argv)
        self.assertIn("/s/boom.wav", argv)
        self.assertIn("/s/boom.wav", retention.sfx_mix_cmd("i", "o", [(1.0, "boom")], "/s"))   # old callers unchanged

    def test_names(self):
        self.assertEqual(lib.clean_name("  Big   laugh.MP3 "), "Big laugh")
        self.assertEqual(lib.clean_name("", "Sound"), "Sound")
        self.assertEqual(len(lib.clean_name("x" * 200)), lib.NAME_MAX)


class UploadChecksTest(unittest.TestCase):
    def test_sniff_ignores_the_extension(self):
        self.assertEqual(lib.sniff(b"RIFF\x00\x00\x00\x00WAVEfmt "), "wav")
        self.assertEqual(lib.sniff(b"OggS\x00\x02"), "ogg")
        self.assertEqual(lib.sniff(b"ID3\x04\x00"), "mp3")
        self.assertEqual(lib.sniff(b"\xff\xfb\x90\x00"), "mp3")
        self.assertIsNone(lib.sniff(b"#EXTM3U\n#EXT-X"))      # an HLS playlist named laugh.mp3
        self.assertIsNone(lib.sniff(b"\x00\x00\x00\x18ftypmp42"))
        self.assertIsNone(lib.sniff(b""))

    def test_commands_force_the_demuxer_and_local_files(self):
        for argv in (lib.probe_cmd("/t/in", "mp3"), lib.measure_cmd("/t/in", "mp3"), lib.convert_cmd("/t/in", "mp3", "/t/o.wav", -2, 2)):
            self.assertEqual(argv[argv.index("-protocol_whitelist") + 1], "file")
            self.assertEqual(argv[argv.index("-f") + 1], "mp3")
        conv = lib.convert_cmd("/t/in", "wav", "/t/o.wav", 3.5, 6)
        self.assertEqual(conv[conv.index("-ac") + 1], "2")
        self.assertIn("volume=3.5dB", conv[conv.index("-af") + 1])

    def test_probe(self):
        a = {"codec_type": "audio", "codec_name": "mp3", "channels": 2}
        ok = lambda d, streams=None: lib.check_probe({"format": {"duration": str(d)}, "streams": streams or [a]})
        self.assertEqual(ok(2.5), (2.5, None))
        self.assertIn("Too long", ok(10.4)[1])
        self.assertIn("Too short", ok(0.1)[1])
        self.assertEqual(ok(2, [a, {"codec_type": "video", "disposition": {"attached_pic": 1}}])[1], None)   # cover art
        self.assertIn("not a video", ok(2, [a, {"codec_type": "video", "disposition": {"attached_pic": 0}}])[1])
        self.assertIn("No audio", ok(2, [{"codec_type": "video"}])[1])
        self.assertIn("Unsupported", ok(2, [{**a, "codec_name": "aac"}])[1])
        self.assertIn("length", lib.check_probe({"format": {"duration": "N/A"}, "streams": [a]})[1])

    def test_level(self):
        mean, peak = lib.parse_volumedetect("[Parsed_volumedetect_1] mean_volume: -24.5 dB\n... max_volume: -10.0 dB")
        self.assertEqual((mean, peak), (-24.5, -10.0))
        self.assertEqual(lib.gain_db(mean, peak), 7.0)       # peak cap (−3) wins over the mean target (+10.5)
        self.assertEqual(lib.gain_db(-8.0, -0.5), -6.0)       # loud → turned down to −14 mean
        self.assertEqual(lib.parse_volumedetect("max_volume: -inf dB"), (None, None))
        self.assertEqual(lib.gain_db(None, None), 0.0)


class FreesoundTest(unittest.TestCase):
    def test_search_params(self):
        p = lib.search_params("laugh")
        self.assertIn('license:"Creative Commons 0"', p["filter"])
        self.assertIn("duration:[0.5 TO 4.0]", p["filter"])
        self.assertNotIn("token", p)        # the key goes in the Authorization header only

    def test_rank_prefers_many_good_votes(self):
        one_perfect = fs(1, rating=5.0, n=1, dl=10)
        crowd = fs(2, rating=4.6, n=200, dl=5000)
        meh = fs(3, rating=3.0, n=50, dl=20000)
        self.assertEqual([c["id"] for c in lib.rank([one_perfect, meh, crowd])][0], 2)

    def test_rank_rechecks_licence_length_and_preview(self):
        res = [fs(1), fs(2, lic="http://creativecommons.org/licenses/by/4.0/"), fs(3, dur=6.0), fs(4, dur=0.2),
               fs(5, preview=False), {"id": "x"}, "junk", {**fs(6), "previews": {"preview-hq-mp3": "https://evil.example/a.mp3"}}]
        self.assertEqual([c["id"] for c in lib.rank(res)], [1])
        self.assertTrue(lib.is_cc0("https://creativecommons.org/publicdomain/zero/1.0"))

    def test_top_n_and_card(self):
        cards = lib.rank([fs(i, rating=3 + i / 10) for i in range(1, 20)])
        self.assertEqual(len(cards), lib.FS_SHOW)
        self.assertEqual(set(cards[0]), {"id", "name", "author", "duration", "license", "url", "rating", "ratings", "downloads"})
        self.assertEqual(cards[0]["license"], "CC0")
        self.assertEqual(cards[0]["name"], "laugh 19")


if __name__ == "__main__":
    unittest.main()
