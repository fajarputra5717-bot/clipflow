#!/usr/bin/env python3
"""Version (owner 2026-10-14): v3.<highest change number in docs/changes/INDEX.md>. Run at every merge to main (and
commit the result in the merge): writes frontend/html/version.json = {version, number, date, entries: latest 5} that
the account menu's version label and "What's new" read. tests/test_version.py fails when the file is stale.

    python3 scripts/write_version.py          # write
    python3 scripts/write_version.py --check  # exit 1 if version.json doesn't match INDEX.md
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/changes/INDEX.md"
OUT = ROOT / "frontend/html/version.json"
MAJOR = 3
LATEST = 5
TITLE_MAX = 160
LINE = re.compile(r"^(\d{3,}) · (\d{4}-\d{2}-\d{2}) · (.+)$")


def entries(text):
    out = []
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        parts = m.group(3).split(" · ")
        title = " · ".join(parts[:-1]) if len(parts) > 1 else parts[0]   # the last part = files touched
        title = title if len(title) <= TITLE_MAX else title[:TITLE_MAX - 1].rstrip() + "…"
        out.append({"number": int(m.group(1)), "date": m.group(2), "title": title})
    return out


def build(text):
    items = sorted(entries(text), key=lambda e: e["number"])
    if not items:
        raise SystemExit("no entries in INDEX.md")
    top = items[-1]
    return {"version": f"v{MAJOR}.{top['number']}", "number": top["number"], "date": top["date"],
            "entries": list(reversed(items[-LATEST:]))}


def main():
    data = build(INDEX.read_text())
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"version.json is stale: expected {data['version']}; run python3 scripts/write_version.py")
            sys.exit(1)
        print(f"version.json ok ({data['version']})")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {data['version']}")


if __name__ == "__main__":
    main()
