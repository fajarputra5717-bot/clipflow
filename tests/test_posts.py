"""shared/posts.py (P2 part 2, 129): run with `python3 -m unittest tests.test_posts` from the repo root."""
import unittest

from shared import posts as p


class Transitions(unittest.TestCase):
    def test_forward_path(self):
        for a, b in (("planned", "posted"), ("posted", "claimed"), ("claimed", "paid")):
            self.assertIsNone(p.transition_problem(a, b))

    def test_drop_and_replan(self):
        for s in ("planned", "posted", "claimed"):
            self.assertIsNone(p.transition_problem(s, "dropped"))
        self.assertIsNone(p.transition_problem("dropped", "planned"))

    def test_refused(self):
        self.assertIn("can't become", p.transition_problem("planned", "paid"))
        self.assertIn("can't become", p.transition_problem("paid", "dropped"))   # paid is final
        self.assertIn("can't become", p.transition_problem("posted", "planned"))
        self.assertIn("Unknown", p.transition_problem("planned", "live"))

    def test_same_status_is_noop(self):
        self.assertIsNone(p.transition_problem("posted", "posted"))


class Urls(unittest.TestCase):
    def test_platform_hosts(self):
        ok = {
            "tiktok": "https://www.tiktok.com/@imeclips/video/7412345678901234567",
            "instagram": "https://www.instagram.com/reel/C9abcDEF/",
            "youtube": "https://youtube.com/shorts/dQw4w9WgXcQ",
            "facebook": "https://www.facebook.com/reel/123",
            "threads": "https://www.threads.net/@x/post/abc",
            "x": "https://x.com/user/status/1",
        }
        for platform, url in ok.items():
            self.assertIsNone(p.url_problem(platform, url), platform)
        self.assertIsNone(p.url_problem("tiktok", None))

    def test_wrong_host_or_scheme(self):
        self.assertIn("isn't on", p.url_problem("tiktok", "https://instagram.com/reel/1"))
        self.assertIn("isn't on", p.url_problem("tiktok", "https://faketiktok.com/v/1"))  # suffix, not subdomain
        self.assertIn("https", p.url_problem("youtube", "http://youtube.com/shorts/x"))
        self.assertIn("https", p.url_problem("youtube", "youtube.com/shorts/x"))


class Fields(unittest.TestCase):
    def test_needs(self):
        self.assertEqual(p.needs("planned"), [])
        self.assertEqual(p.needs("posted"), ["account_id", "url", "posted_at"])
        self.assertEqual(p.needs("dropped"), [])

    def test_rp(self):
        self.assertIsNone(p.rp_problem(12000))
        self.assertIsNone(p.rp_problem(None))
        self.assertIsNotNone(p.rp_problem(-1))
        self.assertIsNotNone(p.rp_problem("12k"))


if __name__ == "__main__":
    unittest.main()


class PublishQueue(unittest.TestCase):
    def test_caption_keeps_hashtags_in_order(self):
        cap, trimmed = p.trim_caption("Gila lompatan ini", ["#ime", "#imeroleplay", "#gta"], 2200)
        self.assertEqual(cap, "Gila lompatan ini\n\n#ime #imeroleplay #gta")
        self.assertFalse(trimmed)

    def test_long_body_trimmed_tags_intact(self):
        body = "kata " * 200
        cap, trimmed = p.trim_caption(body, ["#a", "#b"], 280)
        self.assertTrue(trimmed)
        self.assertLessEqual(len(cap), 280)
        self.assertTrue(cap.endswith("\n\n#a #b"))
        self.assertIn("…", cap)

    def test_no_body_or_no_tags(self):
        self.assertEqual(p.trim_caption("", ["#a"], 100), ("#a", False))
        self.assertEqual(p.trim_caption("hi", [], 100), ("hi", False))

    def test_title_limit(self):
        self.assertEqual(len(p.trim_title("x" * 150, "youtube")), 100)
        self.assertEqual(p.trim_title("x" * 150, "tiktok"), "x" * 150)

    def test_download_name(self):
        self.assertEqual(p.download_name("ime-roleplay", "tiktok", "Lompatan GILA di Kota!"), "ime-roleplay_tiktok_lompatan-gila-di-kota.mp4")
        self.assertEqual(p.download_name(None, "youtube", "Ça va? 🎮"), "clip_youtube_ca-va.mp4")
        self.assertEqual(p.download_name(None, "x", ""), "clip_x_clip.mp4")
