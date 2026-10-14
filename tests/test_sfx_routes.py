"""217 Freesound client with a fake Freesound (no network, no key): run in the backend image
  docker run --rm -v "$PWD:/w" -w /w -e PYTHONPATH=/w:/w/backend --entrypoint python <backend image> -m unittest tests.test_sfx_routes
"""
import os
import unittest
from unittest import mock

try:
    from app import routes_sfx as rs
except Exception:   # no fastapi on the host
    rs = None

CC0 = "http://creativecommons.org/publicdomain/zero/1.0/"


def snd(i, lic=CC0, dur=1.2, rating=4.5, n=20):
    return {"id": i, "name": f"laugh {i}", "username": "fs-user", "license": lic, "duration": dur, "avg_rating": rating,
            "num_ratings": n, "num_downloads": 100 * i, "url": f"https://freesound.org/s/{i}/",
            "previews": {"preview-hq-mp3": f"https://cdn.freesound.org/previews/0/{i}_1-hq.mp3"}}


class Resp:
    def __init__(self, status=200, data=None, body=b""):
        self.status_code, self._data, self._body = status, data, body

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise rs.requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        yield self._body


@unittest.skipUnless(rs, "needs the backend image")
class FreesoundClientTest(unittest.TestCase):
    def setUp(self):
        rs._cache.clear(); rs._previews.clear(); rs._rate.clear()
        self.calls = []
        self.env = mock.patch.dict(os.environ, {"FREESOUND_API_KEY": "fs-secret-key"})
        self.env.start()
        self.core = mock.patch.object(rs, "_core", return_value=mock.Mock(current_user=lambda r: {"id": "u1"}))
        self.core.start()

    def tearDown(self):
        mock.patch.stopall()

    def fake(self, routes):
        def get(url, params=None, timeout=None, headers=None, stream=False):
            self.calls.append((url, params, headers))
            for frag, resp in routes.items():
                if frag in url:
                    return resp
            return Resp(404)
        return mock.patch.object(rs.requests, "get", side_effect=get)

    def test_search_ranks_filters_and_keeps_the_key_in_the_header(self):
        results = [snd(1, rating=5, n=1), snd(2, rating=4.6, n=300), snd(3, lic="http://creativecommons.org/licenses/by/4.0/")]
        with self.fake({"/search/text/": Resp(200, {"results": results})}):
            out = rs.freesound_search(mock.Mock(), category="laugh")
            again = rs.freesound_search(mock.Mock(), category="laugh")
        self.assertEqual([r["id"] for r in out["results"]], [2, 1])        # CC-BY dropped, crowd first
        self.assertEqual(out, again)
        self.assertEqual(len(self.calls), 1)                               # second search came from the cache
        url, params, headers = self.calls[0]
        self.assertEqual(headers, {"Authorization": "Token fs-secret-key"})
        self.assertNotIn("fs-secret-key", url + repr(params))
        self.assertIn('license:"Creative Commons 0"', params["filter"])
        self.assertEqual(params["query"], "laugh")

    def test_errors_never_echo_the_key(self):
        for status, code in ((401, 409), (429, 429), (500, 424)):
            rs._cache.clear()
            with self.fake({"/search/text/": Resp(status, {})}), self.assertRaises(rs.HTTPException) as e:
                rs.freesound_search(mock.Mock(), q="boom")
            self.assertEqual(e.exception.status_code, code)
            self.assertNotIn("fs-secret-key", e.exception.detail)

    def test_no_key(self):
        with mock.patch.dict(os.environ, {"FREESOUND_API_KEY": ""}), self.assertRaises(rs.HTTPException) as e:
            rs.freesound_search(mock.Mock(), category="laugh")
        self.assertEqual(e.exception.status_code, 409)

    def test_save_rechecks_the_sound_itself(self):
        with self.fake({"/sounds/9/": Resp(200, snd(9, lic="http://creativecommons.org/licenses/by/4.0/"))}), \
                self.assertRaises(rs.HTTPException) as e:
            rs._freesound_save({"id": "u1"}, 9, {})
        self.assertIn("Only CC0", e.exception.detail)
        rs._cache.clear()
        with self.fake({"/sounds/9/": Resp(200, snd(9, dur=7.0))}), self.assertRaises(rs.HTTPException):
            rs._freesound_save({"id": "u1"}, 9, {})

    def test_save_downloads_the_hq_preview_with_attribution(self):
        saved = {}
        with self.fake({"/sounds/7/": Resp(200, snd(7)), "cdn.freesound.org/previews/0/7_1-hq.mp3": Resp(200, body=b"ID3mp3")}), \
                mock.patch.object(rs, "_save", side_effect=lambda user, raw, **kw: saved.update(raw=raw, **kw) or {"ok": 1}):
            rs._freesound_save({"id": "u1"}, 7, {"category": "laugh"})
        self.assertEqual(saved["raw"], b"ID3mp3")
        self.assertEqual((saved["source"], saved["author"], saved["license_"], saved["freesound_id"], saved["category"]),
                         ("freesound", "fs-user", CC0, 7, "laugh"))
        self.assertEqual(saved["source_url"], "https://freesound.org/s/7/")
        preview_call = [c for c in self.calls if "cdn.freesound" in c[0]][0]
        self.assertIsNone(preview_call[2])                                  # the key never goes to the CDN

    def test_preview_url_must_be_freesound_cdn(self):
        bad = {**snd(5), "previews": {"preview-hq-mp3": "http://169.254.169.254/latest/meta-data"}}
        with self.fake({"/sounds/5/": Resp(200, bad)}), self.assertRaises(rs.HTTPException) as e:
            rs.freesound_preview(5, mock.Mock())
        self.assertEqual(e.exception.status_code, 400)

    def test_rate_limit(self):
        with self.fake({"/search/text/": Resp(200, {"results": []})}):
            for i in range(rs.RATE["search"][0]):
                rs.freesound_search(mock.Mock(), q=f"word{i}")
            with self.assertRaises(rs.HTTPException) as e:
                rs.freesound_search(mock.Mock(), q="one more")
        self.assertEqual(e.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
