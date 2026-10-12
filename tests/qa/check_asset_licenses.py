#!/usr/bin/env python3
"""Lane C: every bundled Auto Edit asset has a license entry (docs/tasks/auto-edit.md E3).
Usage: check_asset_licenses.py <repo root>   (exit 1 on any gap)
A LICENSES.md (in the file's folder chain under assets/ or worker/assets/) is a markdown table; a row covers a file
when one of its backticked names/globs matches the file's path relative to that LICENSES.md (fnmatch), or the file name
appears in the row. Rules: every row needs a licence name; SFX rows must be CC0/public domain and name a source (URL or
"generated in-house"/script); other rows need a source URL, or an owner/user-supplied statement; CC-BY rows must carry
a credit/attribution text."""
import fnmatch, re, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SKIP = {"LICENSES.md", "README.md", ".gitkeep"}
LIC = re.compile(r"CC0|CC[- ]BY|MIT|OFL|Apache|public domain|own work|owned by|supplied by", re.I)
problems = []
for base in (root / "assets", root / "worker" / "assets"):
    if not base.is_dir():
        continue
    for f in sorted(p for p in base.rglob("*") if p.is_file() and p.name not in SKIP):
        rel = f.relative_to(root)
        row = None
        for d in [f.parent, *f.parents]:
            lic = d / "LICENSES.md"
            if base not in [d, *d.parents] or not lic.is_file():
                continue
            r = f.relative_to(d).as_posix()
            for ln in lic.read_text().splitlines():
                if not ln.startswith("|"):
                    continue
                names = re.findall(r"`([^`]+)`", ln)
                if any(fnmatch.fnmatch(r, n) or r == n for n in names) or (not names and f.name in ln):
                    row = ln
                    break
            if row:
                break
        if not row:
            problems.append(f"{rel}: not covered by any LICENSES.md row")
            continue
        sfx = "sfx" in f.parts
        supplied = re.search(r"supplied by|owned by|own work|not for redistribution", row, re.I)
        if not LIC.search(row):
            problems.append(f"{rel}: row names no licence")
        if sfx and not re.search(r"CC0|public domain", row, re.I):
            problems.append(f"{rel}: SFX row is not CC0")
        if sfx and not (re.search(r"https?://", row) or re.search(r"in-house|generated|scripts/", row, re.I)):
            problems.append(f"{rel}: SFX row names no source")
        if not sfx and not re.search(r"https?://", row) and not supplied:
            problems.append(f"{rel}: row has no source URL")
        if re.search(r"CC[- ]BY", row, re.I) and not re.search(r"©|credit|attribution|by Twemoji", row, re.I):
            problems.append(f"{rel}: CC-BY row has no attribution text")
print("\n".join(problems) or "all assets have a license entry")
sys.exit(1 if problems else 0)
