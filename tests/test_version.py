"""version.json follows docs/changes/INDEX.md (UI phase 1 item 6): `python3 -m unittest tests.test_version`."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("write_version", ROOT / "scripts/write_version.py")
wv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wv)


class VersionTest(unittest.TestCase):
    def test_file_matches_the_index(self):   # a merge that forgot `python3 scripts/write_version.py` fails here
        built = wv.build((ROOT / "docs/changes/INDEX.md").read_text())
        self.assertEqual(json.loads((ROOT / "frontend/html/version.json").read_text()), built)

    def test_scheme(self):
        text = "x\n000 · 2026-09-26 · Base · all\n207 · 2026-10-14 · Fields · index.html\n215 · 2026-10-14 · Editor · usability · editor/*\n"
        d = wv.build(text)
        self.assertEqual((d["version"], d["number"]), ("v3.215", 215))
        self.assertEqual([e["number"] for e in d["entries"]], [215, 207, 0])
        self.assertEqual(d["entries"][0]["title"], "Editor · usability")       # the files part is dropped
        long = wv.build("300 · 2026-10-15 · " + "x" * 300 + " · f\n")["entries"][0]["title"]
        self.assertEqual(len(long), wv.TITLE_MAX)


if __name__ == "__main__":
    unittest.main()
