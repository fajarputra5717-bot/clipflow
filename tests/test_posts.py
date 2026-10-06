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
