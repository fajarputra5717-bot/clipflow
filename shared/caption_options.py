"""Caption catalogue for the Editor page (lane B, P4 task 7a), served in GET …/editor as `captions.options`.

One server-side copy so editor.js keeps no hand-maintained mirror of its own. The style table is the
CSS-preview mirror of make_ass()'s `styles` in worker.py (same rules as scripts/check_caption_mirror.py:
colours equal, preview outline = ASS outline / 2, shadow = ASS shadow > 0, box = BorderStyle 3,
sizeMult = size_mult); tests/test_caption_options.py checks it against worker.py.
"""

from __future__ import annotations

from shared import edit_spec as edit_specs
from shared import fonts

STYLE_PREVIEW = {
    "bold":    {"resting": "#FFFFFF", "highlight": "#FFD60A", "weight": 800, "outline": 3,   "shadow": True,  "box": False, "sizeMult": 1,    "letterSpacing": "0"},
    "outline": {"resting": "#FFFFFF", "highlight": "#FFD60A", "weight": 800, "outline": 4.5, "shadow": True,  "box": False, "sizeMult": 1,    "letterSpacing": "0"},
    "clean":   {"resting": "#FFFFFF", "highlight": "#64D2FF", "weight": 700, "outline": 1.5, "shadow": True,  "box": False, "sizeMult": 0.92, "letterSpacing": "0"},
    "boxed":   {"resting": "#FFFFFF", "highlight": "#FFD60A", "weight": 800, "outline": 1,   "shadow": False, "box": True,  "sizeMult": 1,    "letterSpacing": "0"},
    "hormozi": {"resting": "#FFD60A", "highlight": "#FFD60A", "weight": 900, "outline": 5,   "shadow": False, "box": False, "sizeMult": 1.4,  "letterSpacing": "-.01em"},
    "neon":    {"resting": "#5CE1FF", "highlight": "#FF2D95", "weight": 800, "outline": 2.5, "shadow": True,  "box": False, "sizeMult": 1,    "letterSpacing": "0"},
    "minimal": {"resting": "#FFFFFF", "highlight": "#E8E8ED", "weight": 600, "outline": 1,   "shadow": False, "box": False, "sizeMult": 0.85, "letterSpacing": ".01em"},
    "impact":  {"resting": "#FFFFFF", "highlight": "#FF3B30", "weight": 900, "outline": 2,   "shadow": True,  "box": False, "sizeMult": 1.08, "letterSpacing": "0"},
    "pastel":  {"resting": "#FFF6EC", "highlight": "#FFB4C6", "weight": 700, "outline": 1,   "shadow": True,  "box": False, "sizeMult": 0.95, "letterSpacing": "0"},
    "gold":    {"resting": "#FFFFFF", "highlight": "#FFC300", "weight": 800, "outline": 0.5, "shadow": False, "box": True,  "sizeMult": 1,    "letterSpacing": "0"},
}
STYLE_LABELS = {"bold": "Bold", "outline": "Outline", "clean": "Clean", "boxed": "Boxed", "hormozi": "Hormozi",
                "neon": "Neon", "minimal": "Minimal", "impact": "Impact", "pastel": "Pastel", "gold": "Gold"}
# (id, label, motion family used by the CSS preview: flow = whole line, chunk = word groups, typewriter)
ANIMATIONS = [("karaoke", "Karaoke sweep", "flow"), ("word_pop", "Word pop", "chunk"), ("bounce", "Bounce in", "chunk"),
              ("fade_settle", "Fade & settle", "chunk"), ("typewriter", "Typewriter", "typewriter"),
              ("none", "Static", "flow")]
# Preset cards = fixed style + animation pairs (108's CAPTION_PRESETS; flow-preview step 5 tiles)
PRESETS = [("karaoke", "Karaoke", "outline", "karaoke"), ("pop", "Word pop", "impact", "word_pop"),
           ("hormozi", "Hormozi", "hormozi", "bounce"), ("clean", "Clean", "clean", "fade_settle"),
           ("neon", "Neon", "neon", "typewriter"), ("boxed", "Boxed", "boxed", "word_pop")]
KEYWORD_COLOR_NAMES = {"#FFD60A": "Yellow", "#30D158": "Green", "#FF453A": "Red", "#64D2FF": "Cyan", "#BF5AF2": "Purple"}
SIZE_RANGE = (12, 120)


def options() -> dict:
    return {
        "styles": [{"id": k, "label": STYLE_LABELS[k], **v} for k, v in STYLE_PREVIEW.items()],
        "animations": [{"id": a, "label": n, "family": f} for a, n, f in ANIMATIONS],
        "presets": [{"id": p, "label": n, "style": s, "animation": a} for p, n, s, a in PRESETS],
        "fonts": list(fonts.CAPTION_FONTS),
        "keyword_colors": [{"color": c, "label": KEYWORD_COLOR_NAMES.get(c, c)} for c in edit_specs.KEYWORD_PALETTE],
        "size_range": list(SIZE_RANGE),
        "caption_y_range": list(edit_specs.CAPTION_Y_RANGE),
    }


def auto_keyword_color(style: str) -> str:
    """Keyword colour when none is saved (116): first palette colour that contrasts with the highlight."""
    hi = STYLE_PREVIEW.get(style, STYLE_PREVIEW["bold"])["highlight"]
    return edit_specs.contrasting_keyword_color(hi)
