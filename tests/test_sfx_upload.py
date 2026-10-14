"""217 upload pipeline with real ffmpeg (backend image): sniff → forced-demuxer probe → trim + level → WAV.
Runs where ffmpeg exists (the backend/worker image); skipped elsewhere:
  docker run --rm -v "$PWD:/w" -w /w -e PYTHONPATH=/w:/w/backend --entrypoint python <backend image> -m unittest tests.test_sfx_upload
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make(path, seconds, *, fmt="mp3", vol="0.1", lead_silence=0.0, video=False, src=None):
    src = src or f"sine=frequency=660:duration={seconds}"
    af = f"volume={vol}" + (f",adelay={int(lead_silence * 1000)}:all=1" if lead_silence else "")
    argv = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src]
    if video:
        argv += ["-f", "lavfi", "-i", f"color=c=black:s=64x64:d={seconds}", "-c:v", "libx264" if fmt == "mp4" else "mjpeg"]
    argv += ["-af", af]
    argv += {"mp3": ["-c:a", "libmp3lame"], "wav": ["-c:a", "pcm_s16le"], "ogg": ["-c:a", "libvorbis"],
             "mp4": ["-c:a", "aac"]}[fmt] + ["-f", fmt, str(path)]
    subprocess.run(argv, check=True)
    return path


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg (run in the backend image)")
class UploadPipelineTest(unittest.TestCase):
    def setUp(self):
        from app import routes_sfx
        self.rs = routes_sfx
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def process(self, src):
        return self.rs._process(src, self.tmp / "out.wav")

    def level(self, path):
        p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
        from shared import sfx_library
        return sfx_library.parse_volumedetect(p.stderr)

    def probe(self, path):
        return json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,codec_name,channels:format=duration",
                                          "-of", "json", str(path)], capture_output=True, text=True).stdout)

    def test_each_format_is_levelled_to_wav(self):
        for fmt in ("mp3", "wav", "ogg"):
            with self.subTest(fmt=fmt):
                src = make(self.tmp / f"in.{fmt}", 1.5, fmt=fmt, vol="0.3")
                dur = self.process(src)
                self.assertAlmostEqual(dur, 1.5, delta=0.1)
                info = self.probe(self.tmp / "out.wav")
                self.assertEqual((info["streams"][0]["codec_name"], info["streams"][0]["sample_rate"]), ("pcm_s16le", "48000"))
                mean, peak = self.level(self.tmp / "out.wav")
                self.assertLessEqual(peak, -2.9)                       # never above the bundled peaks
                self.assertAlmostEqual(mean, -14, delta=1.0)

    def test_loud_file_is_turned_down_peak_capped(self):
        self.process(make(self.tmp / "loud.wav", 1.0, fmt="wav", vol="8"))     # clipping-loud input
        mean, peak = self.level(self.tmp / "out.wav")
        self.assertLessEqual(peak, -2.9)
        self.assertLess(mean, -5)

    def test_extension_is_ignored_both_ways(self):
        wav_named_mp3 = make(self.tmp / "laugh.mp3", 1.0, fmt="wav")
        self.assertAlmostEqual(self.process(wav_named_mp3), 1.0, delta=0.1)
        text = self.tmp / "laugh2.mp3"
        text.write_text("#EXTM3U\n#EXTINF:1,\nfile:///etc/passwd\n")
        with self.assertRaises(self.rs.HTTPException) as e:
            self.process(text)
        self.assertEqual(e.exception.status_code, 400)
        self.assertIn("Not an mp3, wav or ogg", e.exception.detail)

    def test_length_rules(self):
        with self.assertRaises(self.rs.HTTPException) as e:
            self.process(make(self.tmp / "long.mp3", 11, fmt="mp3"))
        self.assertIn("Too long", e.exception.detail)
        with self.assertRaises(self.rs.HTTPException) as e:
            self.process(make(self.tmp / "short.wav", 0.2, fmt="wav"))
        self.assertIn("Too short", e.exception.detail)

    def test_lead_silence_is_trimmed(self):
        dur = self.process(make(self.tmp / "gap.wav", 1.0, fmt="wav", lead_silence=0.8))
        self.assertAlmostEqual(dur, 1.0, delta=0.15)

    def test_noise_like_sounds_are_not_silent(self):   # QA cd82e80 Medium: white noise + a burst with a quiet tail
        dur = self.process(make(self.tmp / "white.wav", 1.5, fmt="wav", vol="0.5", src="anoisesrc=color=white:amplitude=0.5:duration=1.5"))
        self.assertAlmostEqual(dur, 1.5, delta=0.1)
        clap = "anoisesrc=color=white:amplitude=0.9:duration=1.2,afade=t=out:st=0.05:d=1.1:curve=exp"
        self.assertGreater(self.process(make(self.tmp / "clap.wav", 1.2, fmt="wav", vol="1", src=clap)), 0.3)

    def test_silent_file(self):
        with self.assertRaises(self.rs.HTTPException) as e:
            self.process(make(self.tmp / "quiet.wav", 1.0, fmt="wav", vol="0"))
        self.assertEqual(e.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
