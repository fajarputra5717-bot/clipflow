"""shared/source_watch.py (P4 task 6): `python3 -m unittest tests.test_source_watch` (no network; yt-dlp is faked)."""
import json
import tempfile
import unittest
from pathlib import Path

from shared import source_watch as sw

CH = "UC" + "a" * 22


def entry(i, status=None, dur=100):
    return {"id": i, "title": f"t{i}", "duration": dur, "live_status": status}


class Fake:
    def __init__(self, videos, streams=(), nofeed=False):
        self.videos, self.streams, self.nofeed, self.calls = list(videos), list(streams), nofeed, []

    def __call__(self, args):
        self.calls.append(args)
        url = args[-1]
        if "--flat-playlist" in args:
            if url.endswith("/videos"):
                return {"channel_id": CH, "entries": self.videos}
            return {"channel_id": CH, "entries": self.streams}
        raise AssertionError("no per-video yt-dlp calls expected")

    def feed(self, channel_id):
        return {} if self.nofeed else {e["id"]: "2023-11-14T22:13:20+00:00" for e in self.videos + self.streams}


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, fake, **kw):
        return sw.check_channel("@FandraOcto", runner=fake, feed=fake.feed, directory=self.d, **kw)

    def test_channel_input(self):
        self.assertEqual(sw.channel_base("@FandraOcto"), "https://www.youtube.com/@FandraOcto")
        self.assertEqual(sw.channel_base("https://www.youtube.com/@FandraOcto/videos"), "https://www.youtube.com/@FandraOcto")
        self.assertEqual(sw.channel_base(CH), f"https://www.youtube.com/channel/{CH}")
        for bad in ("", "https://evil.example/@x", "FandraOcto", "https://youtube.com.evil.io/@x"):
            with self.assertRaises(sw.SourceWatchError):
                sw.channel_base(bad)

    def test_first_check_is_a_baseline(self):
        f = Fake([entry("v1"), entry("v2")])
        self.assertEqual(self.check(f), [])
        self.assertEqual(set(json.loads((self.d / f"{CH}.json").read_text())["seen"]), {"v1", "v2"})

    def test_new_upload_and_finished_stream_returned_once(self):
        self.check(Fake([entry("v1")]))
        f = Fake([entry("v2"), entry("v1")], [entry("s1", "was_live", 9000)])
        got = {x["video_id"]: x for x in self.check(f)}
        self.assertEqual(set(got), {"v2", "s1"})
        self.assertTrue(got["s1"]["is_live_done"])
        self.assertFalse(got["v2"]["is_live_done"])
        self.assertEqual(got["v2"]["url"], "https://www.youtube.com/watch?v=v2")
        self.assertEqual(got["v2"]["duration"], 100)
        self.assertTrue(got["v2"]["published_at"].startswith("2023-11-14"))
        self.assertEqual(self.check(Fake([entry("v2"), entry("v1")], [entry("s1", "was_live")])), [])

    def test_live_stream_waits_until_finished(self):
        self.check(Fake([entry("v1")]))
        self.assertEqual(self.check(Fake([entry("v1")], [entry("s9", "is_live", None)])), [])
        self.assertEqual(self.check(Fake([entry("v1")], [entry("s9", "is_upcoming", None)])), [])
        got = self.check(Fake([entry("v1")], [entry("s9", "was_live", 500)]))
        self.assertEqual([x["video_id"] for x in got], ["s9"])

    def test_feed_failure_keeps_the_video_without_a_date(self):
        self.check(Fake([entry("v1")]))
        got = self.check(Fake([entry("v2"), entry("v1")], nofeed=True))
        self.assertEqual([(x["video_id"], x["published_at"]) for x in got], [("v2", None)])

    def test_backfill_returns_latest_n_on_first_check(self):
        got = self.check(Fake([entry("v3"), entry("v2"), entry("v1")]), backfill=2)
        self.assertEqual([x["video_id"] for x in got], ["v3", "v2"])
        self.assertEqual(self.check(Fake([entry("v3"), entry("v2"), entry("v1")])), [])

    def test_missing_streams_tab_ok_missing_videos_tab_raises(self):
        class NoStreams(Fake):
            def __call__(self, args):
                if args[-1].endswith("/streams"):
                    raise sw.SourceWatchError("404")
                return super().__call__(args)
        self.assertEqual(self.check(NoStreams([entry("v1")])), [])

        class NoVideos(Fake):
            def __call__(self, args):
                raise sw.SourceWatchError("404")
        with self.assertRaises(sw.SourceWatchError):
            self.check(NoVideos([]))

    def test_corrupt_state_rebaselines(self):
        (self.d / f"{CH}.json").write_text("{not json")
        self.assertEqual(self.check(Fake([entry("v1")])), [])


class Hardening(unittest.TestCase):
    """make_runner goes through shared/ytdlp: PO-token args + spacing, cookies retry once on the bot check."""
    BOT = "ERROR: [youtube] x: Sign in to confirm you\u2019re not a bot."

    def run_with(self, results, cookies=None):
        import subprocess
        from unittest import mock
        calls, turns = [], []
        cfg = {"YTDLP_PLAYER_CLIENT": "mweb", "YTDLP_POT_URL": "http://pot:4416", "YTDLP_COOKIES_FILE": cookies or ""}
        it = iter(results)

        def fake_exec(args):
            calls.append(args)
            rc, out, err = next(it)
            return subprocess.CompletedProcess(args, rc, out, err)
        with mock.patch.object(sw, "_exec", fake_exec), mock.patch.object(sw.ytdlp, "wait_turn", lambda s, c=None: turns.append(1)):
            try:
                r = sw.make_runner(cfg.get)(["-J", "u"])
            except sw.SourceWatchError as e:
                r = e
        return r, calls, len(turns)

    def test_args_and_spacing(self):
        r, calls, turns = self.run_with([(0, '{"ok": 1}', "")])
        self.assertEqual(r, {"ok": 1})
        self.assertIn("youtube:player_client=mweb", calls[0])
        self.assertIn("youtubepot-bgutilhttp:base_url=http://pot:4416", calls[0])
        self.assertEqual(turns, 1)

    def test_bot_check_without_cookies_is_a_clear_error(self):
        r, calls, _ = self.run_with([(1, "", self.BOT)])
        self.assertIsInstance(r, sw.SourceWatchError)
        self.assertEqual(str(r), sw.ytdlp.BLOCKED_MESSAGE)
        self.assertEqual(len(calls), 1)

    def test_bot_check_retries_once_with_cookies(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.flush()
            r, calls, turns = self.run_with([(1, "", self.BOT), (0, '{"ok": 2}', "")], cookies=f.name)
            self.assertEqual(r, {"ok": 2})
            self.assertNotIn("--cookies", calls[0])
            self.assertIn("--cookies", calls[1])
            self.assertEqual(turns, 2)
            r, calls, _ = self.run_with([(1, "", self.BOT), (1, "", self.BOT)], cookies=f.name)
            self.assertEqual(str(r), sw.ytdlp.BLOCKED_MESSAGE)
            self.assertEqual(len(calls), 2)




if __name__ == "__main__":
    unittest.main()
