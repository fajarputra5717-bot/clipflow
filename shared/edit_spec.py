"""
Per-clip edits (editor redesign P1, 108+): clip_candidates.edit_spec JSONB.
NULL / missing key = today's behaviour (the job-level setting applies).

Keys so far:
  caption: {style, animation}  per-clip caption preset; overrides the job's
           subtitle_style style/animation (font/size stay job-level).
  keywords: [word, ...]        111: words highlighted in the captions (AI-picked
           at preview build, stoplist-filtered; the user toggles them). An
           explicit [] = "none" (the AI never refills it).
  keyword_color: "#RRGGBB"     111: highlight colour (default KEYWORD_DEFAULT_COLOR).
  caption_y: number            112: caption anchor, % of height from the top (30-85).
           Full-frame clips: replaces FULLFRAME_CAPTION_Y; camera-panel clips:
           never below the seam. Missing = auto (today's placement).

PATCH semantics (main.py update_candidate): top-level keys are merged into
the stored spec; a key sent as null is removed.
"""


def normalize_caption(value, styles, animations):
    """{style, animation} with both validated, or None (= clear)."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("caption must be an object")
    style = str(value.get("style") or "").strip().lower()
    animation = str(value.get("animation") or "").strip().lower()
    if style not in styles:
        raise ValueError(f"unknown caption style: {style!r}")
    if animation not in animations:
        raise ValueError(f"unknown caption animation: {animation!r}")
    return {"style": style, "animation": animation}


import re

KEYWORD_DEFAULT_COLOR = "#FFD60A"
KEYWORD_MAX = 20
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def keyword_token(word):
    """The comparable form of a caption word (case/punctuation-insensitive)."""
    return re.sub(r"[^\w]+", "", str(word or "").lower())


def normalize_keywords(value):
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("keywords must be a list")
    out = []
    for w in value:
        t = keyword_token(w)
        if t and t not in out:
            out.append(t)
    return out[:KEYWORD_MAX]


def normalize_color(value):
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX.match(value.strip()):
        raise ValueError("keyword_color must be #RRGGBB")
    return value.strip().upper()


CAPTION_Y_RANGE = (30.0, 85.0)


def normalize_caption_y(value):
    if value is None:
        return None
    try:
        y = float(value)
    except (TypeError, ValueError):
        raise ValueError("caption_y must be a number (% from top)")
    lo, hi = CAPTION_Y_RANGE
    if not lo <= y <= hi:
        raise ValueError(f"caption_y must be between {lo:g} and {hi:g} % from the top")
    return round(y, 1)


def keywords_of(spec):
    """(set of tokens, '#RRGGBB') from a stored spec; empty set when none."""
    spec = spec if isinstance(spec, dict) else {}
    return set(spec.get("keywords") or []), spec.get("keyword_color") or KEYWORD_DEFAULT_COLOR


def normalize_patch(patch, styles, animations):
    """-> (merge dict, keys to remove). Unknown keys raise ValueError."""
    if not isinstance(patch, dict):
        raise ValueError("edit_spec must be an object")
    merge, remove = {}, []
    for key, value in patch.items():
        if key == "caption":
            value = normalize_caption(value, styles, animations)
        elif key == "keywords":
            value = normalize_keywords(value)
        elif key == "keyword_color":
            value = normalize_color(value)
        elif key == "caption_y":
            value = normalize_caption_y(value)
        else:
            raise ValueError(f"unknown edit_spec key: {key!r}")
        if value is None:
            remove.append(key)
        else:
            merge[key] = value
    return merge, remove


def caption_override(spec):
    """(style, animation) from a stored spec, or (None, None)."""
    cap = (spec or {}).get("caption") if isinstance(spec, dict) else None
    if not isinstance(cap, dict):
        return None, None
    return cap.get("style") or None, cap.get("animation") or None
