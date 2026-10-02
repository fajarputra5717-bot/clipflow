#!/usr/bin/env python3
"""
Caption mirror check (108): index.html's SUBTITLE_STYLE_PREVIEW / SUBTITLE_ANIMATIONS /
CAPTION_PRESETS must match make_ass() in worker.py (the live CSS preview and the preset
cards are a hand-maintained mirror of the ASS styles). Run: python3 scripts/check_caption_mirror.py
Rules: colours equal; preview outline = ASS outline / 2; shadow = ASS shadow > 0;
box = ASS BorderStyle 3; sizeMult = size_mult; same style + animation names.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
worker = (ROOT / "worker/worker.py").read_text()
html = (ROOT / "frontend/html/index.html").read_text()


def hexnorm(c):
    c = c.strip().strip('"\'').lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


m = re.search(r"\n    styles = (\{.*?\n    \})\n", worker, re.S)
ass = ast.literal_eval(m.group(1))
anims = re.search(r"\nANIMATIONS = \{(.*?)\n\}", worker, re.S).group(1)
ass_anims = set(re.findall(r'^\s{4}"([a-z_]+)":', anims, re.M))

prev = {}
block = re.search(r"const SUBTITLE_STYLE_PREVIEW=\{(.*?)\n\};", html, re.S).group(1)
for name, body in re.findall(r"^\s*([a-z]+):\{(.*?)\}", block, re.M):
    prev[name] = dict(re.findall(r"(\w+):(\"[^\"]*\"|[^,]+)", body))
ui_anims = set(re.findall(r'\["([a-z_]+)","[^"]+","[a-z]+"\]', re.search(
    r"const SUBTITLE_ANIMATIONS=\[(.*?)\];", html, re.S).group(1)))
presets = re.findall(r'\["[a-z]+","[^"]+","([a-z]+)","([a-z_]+)"\]', re.search(
    r"const CAPTION_PRESETS=\[(.*?)\];", html, re.S).group(1))

errors = []
if set(ass) != set(prev):
    errors.append(f"style names differ: ASS {sorted(set(ass) - set(prev))} vs preview {sorted(set(prev) - set(ass))}")
for name in sorted(set(ass) & set(prev)):
    a, p = ass[name], prev[name]
    checks = [
        ("resting", hexnorm(a["resting"]), hexnorm(p["resting"])),
        ("highlight", hexnorm(a["highlight"]), hexnorm(p["highlight"])),
        ("outline/2", a["outline"] / 2, float(p["outline"])),
        ("shadow", a["shadow"] > 0, p["shadow"] == "true"),
        ("box", a["border_style"] == 3, p["box"] == "true"),
        ("sizeMult", float(a["size_mult"]), float(p["sizeMult"])),
    ]
    for what, want, got in checks:
        if want != got:
            errors.append(f"{name}.{what}: make_ass {want!r} vs preview {got!r}")
if ass_anims != ui_anims:
    errors.append(f"animations differ: ASS {sorted(ass_anims)} vs UI {sorted(ui_anims)}")
for st, an in presets:
    if st not in ass or an not in ass_anims:
        errors.append(f"preset uses unknown style/animation: {st} + {an}")

print(f"{len(ass)} styles, {len(ass_anims)} animations, {len(presets)} presets checked")
if errors:
    print("MISMATCH:\n  " + "\n  ".join(errors))
    sys.exit(1)
print("OK: preview mirror matches make_ass()")
