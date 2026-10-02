"""Unit tests for shared/retention.py (pure; no ffmpeg). Run: python -m unittest tests.test_retention"""

import unittest

from shared import retention as r

SILENCEDETECT = """
[silencedetect @ 0x1] silence_start: 2.01
[silencedetect @ 0x1] silence_end: 3.52 | silence_duration: 1.51
[silencedetect @ 0x1] silence_start: 7.4
[silencedetect @ 0x1] silence_end: 7.8 | silence_duration: 0.4
[silencedetect @ 0x1] silence_start: 9.0
"""

LOUDNORM = """[Parsed_loudnorm_0 @ 0x2]
{
	"input_i" : "-23.41",
	"input_tp" : "-4.10",
	"input_lra" : "6.20",
	"input_thresh" : "-33.80",
	"output_i" : "-14.02",
	"output_tp" : "-1.00",
	"output_lra" : "5.10",
	"output_thresh" : "-24.40",
	"normalization_type" : "dynamic",
	"target_offset" : "0.02"
}
"""


class SilenceTrim(unittest.TestCase):
    def test_parse_with_open_tail(self):
        self.assertEqual(r.parse_silencedetect(SILENCEDETECT, 10.0),
                         [(2.01, 3.52), (7.4, 7.8), (9.0, 10.0)])

    def test_keep_respects_pad_and_min_gap(self):
        keep = r.plan_keep_segments(10.0, [(2.0, 3.5), (7.4, 7.8)], min_gap=0.5, pad=0.1)
        # 2.0-3.5 shrinks to 2.1-3.4 (cut); 7.4-7.8 shrinks to 0.2 s < min_gap (kept)
        self.assertEqual(keep, [(0.0, 2.1), (3.4, 10.0)])

    def test_silence_never_cuts_into_a_word(self):
        words = [{"word": "late", "start": 2.0, "end": 2.6}]
        keep = r.plan_keep_segments(10.0, [(1.5, 4.0)], words=words, min_gap=0.5, pad=0.0, word_pad=0.05)
        # 1.5-1.95 (before the word) is < min_gap so it stays; only 2.65-4.0 (after word + pad) is cut
        self.assertEqual(keep, [(0.0, 2.65), (4.0, 10.0)])

    def test_forced_cut_removes_a_filler_word(self):
        keep = r.plan_keep_segments(6.0, words=[{"word": "um", "start": 2.0, "end": 2.3}],
                                    forced_cuts=[(2.0, 2.3)])
        self.assertEqual(keep, [(0.0, 2.0), (2.3, 6.0)])

    def test_frame_snapping_and_window(self):
        keep = r.plan_keep_segments(10.0, [(2.013, 3.517)], pad=0.0, fps=30, window=(0.51, 9.0))
        for s, e in keep:
            self.assertAlmostEqual(s * 30, round(s * 30), places=6)
            self.assertAlmostEqual(e * 30, round(e * 30), places=6)
        self.assertGreaterEqual(keep[0][0], 0.5)
        self.assertLessEqual(keep[-1][1], 9.0)

    def test_default_off(self):
        self.assertFalse(r.SILENCE_TRIM_DEFAULT)

    def test_word_gaps(self):
        words = [{"word": "a", "start": 0.0, "end": 0.5}, {"word": "b", "start": 0.9, "end": 1.2},
                 {"word": "c", "start": 2.0, "end": 2.4}, {"word": "d", "start": 2.3, "end": 3.0},
                 {"word": "e", "start": 3.7, "end": 4.0}]
        # 0.4 gap ignored; 0.8 gap cut; overlapping c/d never gap; 0.7 gap after d's end
        self.assertEqual(r.word_gap_silences(words, min_gap=0.6), [(1.2, 2.0), (3.0, 3.7)])
        keep = r.plan_word_gap_keep(5.0, words, min_gap=0.6, pad=0.12)
        self.assertEqual([(round(a, 2), round(b, 2)) for a, b in keep], [(0.0, 1.32), (1.88, 3.12), (3.58, 5.0)])
        self.assertEqual(r.plan_word_gap_keep(5.0, words, min_gap=1.0), [(0.0, 5.0)])

    def test_crossfade_graph_keeps_length(self):
        keep = [(0.0, 2.0), (3.0, 5.0), (6.0, 8.0)]
        g = r.silence_trim_graph(keep, crossfade=0.04, duration=9.0)
        self.assertIn("[sa0]atrim=start=0:end=2.02", g)
        self.assertIn("[sa1]atrim=start=2.98:end=5.02", g)
        self.assertIn("[sa2]atrim=start=5.98:end=8,", g)
        self.assertIn("[a0][a1]acrossfade=d=0.04:c1=qsin:c2=qsin[x1]", g)
        self.assertIn("[x1][a2]acrossfade=d=0.04:c1=qsin:c2=qsin[atrim]", g)
        self.assertIn("concat=n=3:v=1:a=0[vtrim]", g)
        audio = (2.02 - 0) + (5.02 - 2.98) + (8 - 5.98) - 2 * 0.04
        self.assertAlmostEqual(audio, sum(e - s for s, e in keep))

    def test_graph_shape(self):
        g = r.silence_trim_graph([(0.0, 2.0), (3.0, 5.0)], crossfade=0)
        self.assertIn("[0:v]split=2[sv0][sv1]", g)
        self.assertIn("[0:a]asplit=2[sa0][sa1]", g)
        self.assertIn("atrim=start=3:end=5", g)
        self.assertIn("[v0][v1]concat=n=2:v=1:a=0[vtrim]", g)
        self.assertTrue(g.endswith("[a0][a1]concat=n=2:v=0:a=1[atrim]"))
        with self.assertRaises(ValueError):
            r.silence_trim_graph([])


class WordTiming(unittest.TestCase):
    keep = [(0.0, 2.0), (3.0, 5.0), (6.0, 8.0)]

    def test_timemap(self):
        tm = r.TimeMap(self.keep)
        self.assertEqual(tm.duration, 6.0)
        self.assertEqual(tm.to_output(1.0), 1.0)
        self.assertIsNone(tm.to_output(2.5))
        self.assertEqual(tm.to_output(3.5), 2.5)
        self.assertEqual(tm.to_output_clamped(2.5), 2.0)
        self.assertEqual(tm.to_output_clamped(9.0), 6.0)

    def test_remap_words(self):
        words = [{"word": "a", "start": 0.5, "end": 0.9},
                 {"word": "gone", "start": 2.2, "end": 2.8},          # fully cut -> dropped
                 {"word": "b", "start": 3.1, "end": 3.4, "p": 0.9},   # extra keys survive
                 {"word": "span", "start": 4.8, "end": 6.2}]          # straddles a cut
        out = r.remap_words(words, self.keep)
        self.assertEqual([w["word"] for w in out], ["a", "b", "span"])
        self.assertEqual((out[1]["start"], out[1]["end"], out[1]["p"]), (2.1, 2.4, 0.9))
        self.assertEqual((out[2]["start"], out[2]["end"]), (3.8, 4.2))  # 0.2 + 0.2 kept
        for w in out:
            self.assertLess(w["start"], w["end"])

    def test_zero_length_word_kept(self):
        out = r.remap_words([{"word": "x", "start": 3.5, "end": 3.5}, {"word": "cut", "start": 2.5, "end": 2.5}],
                            self.keep)
        self.assertEqual([(w["word"], w["start"], w["end"]) for w in out], [("x", 2.5, 2.52)])

    def test_remap_times(self):
        self.assertEqual(r.remap_times([1.0, 2.5, 7.0], self.keep), [1.0, 2.0, 5.0])


class Zoom(unittest.TestCase):
    def test_windows_merge_and_clip(self):
        w = r.plan_zoom_windows([1.0, 1.5, 10.0, -1, 30], 12.0, ramp=0.25, hold=1.0)
        self.assertEqual(w, [(1.0, 3.0), (10.0, 11.5)])

    def test_expr_and_filter(self):
        self.assertIsNone(r.zoom_filter([]))
        self.assertEqual(r.zoom_expr([]), "1")
        f = r.zoom_filter([(1.0, 2.5)], peak=1.15)
        self.assertIn("eval=frame", f)
        self.assertIn("crop=1080:1920", f)
        self.assertIn("1+0.15*ld(1)", f)

    def test_expr_values(self):
        """Evaluate the expression in Python to check the curve: 1.0 -> 1.15 -> 1.0, monotone ramps."""
        expr = r.zoom_expr([(1.0, 2.5)], peak=1.15, ramp=0.25)

        def z(t):
            reg = {}
            env = {"t": t, "clip": lambda x, a, b: max(a, min(b, x)), "min": min,
                   "st": lambda i, v: reg.__setitem__(i, v) or v, "ld": lambda i: reg[i]}
            val = None
            for term in expr.split(";"):
                val = eval(term, {"__builtins__": {}}, env)  # noqa: S307 - own test string
            return val

        self.assertAlmostEqual(z(0.5), 1.0)
        self.assertAlmostEqual(z(1.125), 1.075)          # half-way up the smoothstep
        self.assertAlmostEqual(z(1.8), 1.15)
        self.assertAlmostEqual(z(3.0), 1.0)
        ups = [z(1.0 + i * 0.025) for i in range(11)]
        self.assertEqual(ups, sorted(ups))


class Loudnorm(unittest.TestCase):
    def test_relative_noise(self):
        self.assertEqual(r.relative_noise_db(-14.0), -28.0)
        self.assertEqual(r.relative_noise_db(-5.0), -25.0)
        self.assertEqual(r.relative_noise_db(None), r.SILENCE_NOISE_DB)

    def test_parse_ebur128(self):
        e = ("[Parsed_ebur128_0 @ 0x1] t: 1.2 M: -20 S: -20 I: -30.0 LUFS\n"
             "[Parsed_ebur128_0 @ 0x1] Summary:\n\n  Integrated loudness:\n    I:         -14.1 LUFS\n"
             "    Threshold: -24.4 LUFS\n\n  True peak:\n    Peak:       -1.2 dBFS\n")
        self.assertEqual(r.parse_ebur128(e), {"i": -14.1, "tp": -1.2})
        self.assertIsNone(r.parse_ebur128("nothing"))

    def test_parse(self):
        m = r.parse_loudnorm(LOUDNORM)
        self.assertEqual(m["input_i"], -23.41)
        self.assertEqual(m["target_offset"], 0.02)

    def test_parse_silent_or_garbage(self):
        self.assertIsNone(r.parse_loudnorm(LOUDNORM.replace('"-23.41"', '"-inf"')))
        self.assertIsNone(r.parse_loudnorm(LOUDNORM.replace('"-23.41"', '"-80.0"')))
        self.assertIsNone(r.parse_loudnorm("no json here"))

    def test_filter(self):
        f = r.loudnorm_filter(r.parse_loudnorm(LOUDNORM))
        self.assertTrue(f.startswith("loudnorm=I=-14:TP=-1:LRA=11:measured_I=-23.41"))
        self.assertIn("linear=true", f)
        self.assertTrue(f.endswith("alimiter=limit=0.8414:attack=1:release=50:level=0,aresample=48000,"
                                   "aformat=channel_layouts=mono|stereo"))
        self.assertTrue(r.loudnorm_filter(None).startswith("aresample=192000,alimiter"))

    def test_two_pass_cmds(self):
        m = r.loudnorm_measure_cmd("in.mp4").argv
        self.assertIn("loudnorm=I=-14:TP=-1:LRA=11:print_format=json", m)
        a = r.loudnorm_apply_cmd("in.mp4", "out.mp4", None).argv
        self.assertEqual(a[a.index("-c:v") + 1], "copy")
        self.assertEqual(a[-1], "out.mp4")


class Combined(unittest.TestCase):
    def test_trim_zoom_maps(self):
        a = r.trim_zoom_cmd("i.mp4", "o.mp4", keep=[(0, 1), (2, 3)], zoom_windows=[(0.2, 1.5)]).argv
        self.assertIn("[vtrim]scale=", a[a.index("-filter_complex") + 1])
        self.assertEqual(a[a.index("-map") + 1], "[vzoom]")
        self.assertIn("[atrim]", a)
        plain = r.trim_zoom_cmd("i.mp4", "o.mp4").argv
        self.assertNotIn("-filter_complex", plain)
        self.assertIn("0:a?", plain)


if __name__ == "__main__":
    unittest.main()
