"""shared/view_pull.py (P5 part 1): `python3 -m unittest tests.test_view_pull`."""
import unittest
from datetime import datetime, timedelta, timezone

from shared import view_pull as vp

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


def post(days=1, pulled_h=None, platform="youtube"):
    return {"platform": platform, "posted_at": NOW - timedelta(days=days),
            "views_pulled_at": None if pulled_h is None else NOW - timedelta(hours=pulled_h)}


class ViewPullTest(unittest.TestCase):
    def test_youtube_id(self):
        self.assertEqual(vp.youtube_id("https://www.youtube.com/shorts/AbC_dEf-123"), "AbC_dEf-123")
        self.assertEqual(vp.youtube_id("https://youtube.com/watch?feature=x&v=AbC_dEf-123"), "AbC_dEf-123")
        self.assertEqual(vp.youtube_id("https://youtu.be/AbC_dEf-123?si=q"), "AbC_dEf-123")
        self.assertEqual(vp.youtube_id("https://example.com/x", "AbC_dEf-123"), "AbC_dEf-123")
        self.assertIsNone(vp.youtube_id("https://www.tiktok.com/@a/video/1"))
        self.assertIsNone(vp.youtube_id(None, "nope"))

    def test_cadence(self):
        self.assertTrue(vp.due(post(1), NOW))                        # never pulled
        self.assertFalse(vp.due(post(1, pulled_h=2), NOW))           # < 14 days: every 6 h
        self.assertTrue(vp.due(post(1, pulled_h=6), NOW))
        self.assertFalse(vp.due(post(20, pulled_h=12), NOW))         # 14–30 days: daily
        self.assertTrue(vp.due(post(20, pulled_h=24), NOW))
        self.assertFalse(vp.due(post(30), NOW))                      # ≥ 30 days: stop
        self.assertFalse(vp.due(post(1, platform="tiktok"), NOW))    # manual platforms
        self.assertFalse(vp.due({"platform": "youtube", "posted_at": None}, NOW))

    def test_batches_and_parse(self):
        b = vp.batches([f"id{i:08d}" for i in range(120)] + ["id00000000"])
        self.assertEqual([len(x) for x in b], [50, 50, 20])
        data = {"items": [{"id": "a", "statistics": {"viewCount": "1234"}}, {"id": "b", "statistics": {}}, {"id": "c"}]}
        self.assertEqual(vp.parse_counts(data), {"a": 1234})

    def test_quota_day_and_errors(self):
        start = vp.quota_day_start(NOW)                                # 10:00 UTC = 03:00 PDT
        self.assertEqual((start.hour, start.day), (0, 12))
        self.assertEqual(vp.next_quota_reset(NOW).astimezone(vp.PACIFIC).strftime("%d %H:%M"), "13 00:00")
        q = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        self.assertEqual(vp.error_kind(403, q), "quota")
        self.assertEqual(vp.error_kind(400, {"error": {"errors": [{"reason": "keyInvalid"}]}}), "key")
        self.assertEqual(vp.error_kind(403, {"error": {"errors": [{"reason": "accessNotConfigured"}]}}), "key")
        self.assertEqual(vp.error_kind(503, None), "transient")
        self.assertEqual(vp.error_kind(403, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}), "transient")   # QA Low 1
        self.assertEqual(vp.error_kind(400, {"error": {"message": "API key not valid. Please pass a valid API key.",
                                                       "errors": [{"reason": "badRequest"}]}}), "key")
        self.assertEqual(vp.error_kind(400, {"error": {"errors": [{"reason": "invalidParameter"}]}}), "request")    # QA Low 2


class MetaRulesTest(unittest.TestCase):   # 199
    def test_ids(self):
        self.assertEqual(vp.instagram_shortcode("https://www.instagram.com/reel/C9xYz_12-ab/?igsh=x"), "C9xYz_12-ab")
        self.assertEqual(vp.instagram_shortcode("https://instagram.com/fanig/reel/C9xYz12ab/"), "C9xYz12ab")
        self.assertEqual(vp.instagram_shortcode("https://www.instagram.com/p/C9xYz12ab"), "C9xYz12ab")
        self.assertIsNone(vp.instagram_shortcode("https://www.instagram.com/fanig/"))
        self.assertEqual(vp.facebook_video_id("https://www.facebook.com/reel/1234567890123"), "1234567890123")
        self.assertEqual(vp.facebook_video_id("https://www.facebook.com/fanpage/videos/987654321012/"), "987654321012")
        self.assertEqual(vp.facebook_video_id("https://www.facebook.com/watch/?v=555666777888"), "555666777888")
        self.assertEqual(vp.facebook_video_id("https://fb.watch/abc/", "1234567"), "1234567")
        self.assertIsNone(vp.facebook_video_id("https://fb.watch/abc/"))

    def test_cadence_covers_meta(self):
        self.assertTrue(vp.due(post(1, platform="instagram"), NOW))
        self.assertFalse(vp.due(post(1, pulled_h=2, platform="facebook"), NOW))

    def test_parse(self):
        self.assertEqual(vp.ig_views({"data": [{"name": "views", "period": "lifetime", "values": [{"value": 4321}]}]}), 4321)
        self.assertEqual(vp.ig_views({"data": [{"name": "views", "total_value": {"value": "77"}}]}), 77)
        self.assertIsNone(vp.ig_views({"data": []}))
        both = {"data": [{"name": "blue_reels_play_count", "values": [{"value": 10}]},
                         {"name": "fb_reels_total_plays", "values": [{"value": 15}]}]}
        self.assertEqual(vp.fb_plays(both), 15)
        self.assertEqual(vp.fb_plays({"data": [{"name": "blue_reels_play_count", "values": [{"value": 10}]}]}), 10)
        self.assertEqual(len(vp.token_hash("abc")), 16)

    def test_errors(self):
        e = lambda code, **kw: {"error": {"code": code, **kw}}
        self.assertEqual(vp.meta_error_kind(400, e(190)), "key")          # expired / invalid token
        self.assertEqual(vp.meta_error_kind(403, e(200)), "key")          # permission missing on /me/accounts
        self.assertEqual(vp.meta_error_kind(400, e(10)), "key")
        self.assertEqual(vp.meta_error_kind(403, e(200), per_object=True), "request")   # QA 199 Low 2: one object
        self.assertEqual(vp.meta_error_kind(400, e(10), per_object=True), "request")
        self.assertEqual(vp.meta_error_kind(400, e(190), per_object=True), "key")
        self.assertEqual(vp.meta_error_kind(400, e(4)), "transient")      # app rate limit
        self.assertEqual(vp.meta_error_kind(400, e(80002)), "transient")  # Instagram BUC limit
        self.assertEqual(vp.meta_error_kind(500, None), "transient")
        self.assertEqual(vp.meta_error_kind(400, e(100, error_subcode=33)), "request")   # not ours / no such object


if __name__ == "__main__":
    unittest.main()
