#!/usr/bin/env python3
"""Lane C: every bundled Auto Edit asset has a license entry (docs/tasks/auto-edit.md E3).
Usage: check_asset_licenses.py <repo root>   (exit 1 on any gap)
SFX under assets/sfx/: file must be named in assets/sfx/LICENSES.md with source URL + author + CC0.
Other overlay/emoji assets under assets/: named in assets/LICENSES.md (or the folder's LICENSES.md) with URL + licence; an owner/user-supplied file (e.g. worker/assets/watermark.png) may carry a "supplied by / owned by / not for redistribution" statement instead."""
import re, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SKIP = {"LICENSES.md", "README.md", ".gitkeep"}
problems = []
for base in (root / "assets", root / "worker" / "assets"):
    if not base.is_dir():
        continue
    for f in sorted(p for p in base.rglob("*") if p.is_file() and p.name not in SKIP):
        rel = f.relative_to(root)
        docs = [d / "LICENSES.md" for d in [f.parent, *f.parents] if (d / "LICENSES.md").is_file() and base in [d, *d.parents]]
        if not docs:
            problems.append(f"{rel}: no LICENSES.md in its folder chain")
            continue
        entry = next((ln for d in docs for ln in d.read_text().splitlines() if f.name in ln), None)
        if not entry:
            problems.append(f"{rel}: not listed in {docs[0].relative_to(root)}")
            continue
        supplied = re.search(r"supplied by|owned by|own work|not for redistribution", entry, re.I)   # user/owner-supplied files: a statement replaces URL + licence
        if not re.search(r"https?://", entry) and not (supplied and "sfx" not in f.parts):
            problems.append(f"{rel}: entry has no source URL")
        if "sfx" in f.parts and not re.search(r"CC0|public domain", entry, re.I):
            problems.append(f"{rel}: SFX entry is not CC0")
        if not re.search(r"CC0|CC[- ]BY|MIT|OFL|Apache|public domain|own work", entry, re.I) and not (supplied and "sfx" not in f.parts):
            problems.append(f"{rel}: entry names no licence")
print("\n".join(problems) or "all assets have a license entry")
sys.exit(1 if problems else 0)
