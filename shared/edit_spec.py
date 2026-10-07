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

  hook_title: {on, text, duration}   P4 task 1 (lane B): title card over the first seconds.
           text "" / missing = the clip's title; duration ∈ {2, 2.5, 3} s (default 2.5).
           Rendered by worker/render_steps.add_title_card() in preview and final.
  cuts: {trim: [a, b] | null, removed: [[s, e], ...]}   P4 task 3 (lane B): clip-relative SOURCE
           seconds. trim = the kept window (null = whole clip); removed = cut words/pauses inside it.
           Applied after the render (render_steps.apply_cuts), so burned captions are cut with the video.
  zoom: {on, intensity, markers: [s, ...]}   P4 task 4 (lane B): punch-ins at SOURCE seconds; intensity
           0–100 (peak scale 1.0–1.30, default 50 = 1.15). Rendered inside render_vertical before the
           watermark/captions (render_steps.zoom_stage), so text never zooms.

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
# 116: palette order (= the UI swatches); an unset colour defaults to the first
# one that clearly differs from the caption style's highlight colour.
KEYWORD_PALETTE = ["#FFD60A", "#30D158", "#FF453A", "#64D2FF", "#BF5AF2"]


def _rgb(h):
    h = str(h).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrasting_keyword_color(highlight, min_distance=120):
    """First palette colour at least min_distance (RGB) away from the style highlight."""
    try:
        hi = _rgb(highlight)
    except (ValueError, TypeError):
        return KEYWORD_DEFAULT_COLOR
    for c in KEYWORD_PALETTE:
        if sum((a - b) ** 2 for a, b in zip(_rgb(c), hi)) ** 0.5 >= min_distance:
            return c
    return KEYWORD_DEFAULT_COLOR
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
    """(set of tokens, '#RRGGBB' or None) from a stored spec; None colour = auto
    (116: make_ass picks a colour that contrasts with the style highlight)."""
    spec = spec if isinstance(spec, dict) else {}
    return set(spec.get("keywords") or []), spec.get("keyword_color") or None


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
        elif key == "hook_title":
            value = normalize_hook_title(value)
        elif key == "cuts":
            value = normalize_cuts(value)
        elif key == "zoom":
            value = normalize_zoom(value)
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


# ---- hook title card (P4 task 1, lane B)

HOOK_TITLE_DURATIONS = (2.0, 2.5, 3.0)
HOOK_TITLE_DEFAULT_DURATION = 2.5
HOOK_TITLE_MAX_CHARS = 80


def normalize_hook_title(value):
    """{on: bool, text: str ('' = clip title), duration: 2|2.5|3} or None (= clear)."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("hook_title must be an object")
    text = " ".join(str(value.get("text") or "").split())
    if len(text) > HOOK_TITLE_MAX_CHARS:
        raise ValueError(f"hook_title.text is longer than {HOOK_TITLE_MAX_CHARS} characters")
    try:
        duration = float(value.get("duration", HOOK_TITLE_DEFAULT_DURATION))
    except (TypeError, ValueError):
        raise ValueError("hook_title.duration must be a number")
    if duration not in HOOK_TITLE_DURATIONS:
        raise ValueError(f"hook_title.duration must be one of {HOOK_TITLE_DURATIONS}")
    return {"on": bool(value.get("on", True)), "text": text, "duration": duration}


def hook_title_of(spec):
    """The stored hook_title dict, or None."""
    ht = (spec or {}).get("hook_title") if isinstance(spec, dict) else None
    return ht if isinstance(ht, dict) else None


# ---- cuts (P4 task 3, lane B)

CUTS_MAX_RANGES = 400
CUT_MIN_LEN = 0.04          # shorter removals are dropped (below one frame-ish + crossfade)
OUTPUT_MIN_SECONDS = 1.0


def _merge_ranges(ranges):
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + 1e-3:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def normalize_cuts(value, clip_duration=None):
    """{trim: [a, b] | None, removed: [[s, e], ...]} (sorted, merged, clamped to the trim window,
    3 decimals) or None (= clear). clip_duration (seconds) enables bounds + minimum-output checks."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("cuts must be an object")
    hi = float(clip_duration) if clip_duration else None
    trim = value.get("trim")
    if trim is not None:
        try:
            a, b = (round(float(x), 3) for x in trim)
        except (TypeError, ValueError):
            raise ValueError("cuts.trim must be [start, end] in seconds")
        a = max(0.0, a)
        if hi is not None:
            b = min(hi, b)
        if b - a < OUTPUT_MIN_SECONDS:
            raise ValueError("cuts.trim keeps less than 1 second")
        trim = [a, b]
        if hi is not None and a <= 0.0005 and b >= hi - 0.0005:
            trim = None                       # the whole clip: same as no trim
    lo_w, hi_w = (trim or [0.0, hi if hi is not None else float("inf")])
    raw = value.get("removed") or []
    if not isinstance(raw, list) or len(raw) > CUTS_MAX_RANGES:
        raise ValueError(f"cuts.removed must be a list of at most {CUTS_MAX_RANGES} [start, end] ranges")
    ranges = []
    for r in raw:
        try:
            s, e = (round(float(x), 3) for x in r)
        except (TypeError, ValueError):
            raise ValueError("cuts.removed entries must be [start, end] in seconds")
        s, e = max(s, lo_w), min(e, hi_w)
        if e - s >= CUT_MIN_LEN:
            ranges.append([s, e])
    removed = _merge_ranges(ranges)
    if hi is not None:
        kept = (hi_w - lo_w) - sum(e - s for s, e in removed)
        if kept < OUTPUT_MIN_SECONDS:
            raise ValueError("cuts remove (almost) the whole clip")
    if trim is None and not removed:
        return None
    return {"trim": trim, "removed": removed}


def cuts_of(spec):
    """The stored cuts dict, or None."""
    c = (spec or {}).get("cuts") if isinstance(spec, dict) else None
    return c if isinstance(c, dict) and (c.get("trim") or c.get("removed")) else None


# ---- zoom punch-ins (P4 task 4, lane B)

ZOOM_MAX_MARKERS = 40
ZOOM_DEFAULT_INTENSITY = 50


def normalize_zoom(value, clip_duration=None):
    """{on, intensity, markers} (markers sorted, de-duplicated to 0.05 s, inside the clip) or None."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("zoom must be an object")
    try:
        intensity = int(round(float(value.get("intensity", ZOOM_DEFAULT_INTENSITY))))
    except (TypeError, ValueError):
        raise ValueError("zoom.intensity must be a number 0–100")
    if not 0 <= intensity <= 100:
        raise ValueError("zoom.intensity must be 0–100")
    raw = value.get("markers") or []
    if not isinstance(raw, list) or len(raw) > ZOOM_MAX_MARKERS:
        raise ValueError(f"zoom.markers must be a list of at most {ZOOM_MAX_MARKERS} times")
    marks = []
    for m in raw:
        try:
            t = round(float(m), 2)
        except (TypeError, ValueError):
            raise ValueError("zoom.markers must be seconds")
        if t < 0 or (clip_duration is not None and t >= float(clip_duration)):
            continue
        if not marks or abs(t - marks[-1]) >= 0.05:
            marks.append(t)
    marks = sorted(set(marks))
    on = bool(value.get("on", True))
    if not marks and intensity == ZOOM_DEFAULT_INTENSITY and on:
        return None
    return {"on": on, "intensity": intensity, "markers": marks}


def zoom_of(spec):
    z = (spec or {}).get("zoom") if isinstance(spec, dict) else None
    return z if isinstance(z, dict) else None


def zoom_peak(intensity):
    """0–100 → peak scale 1.0–1.30 (50 → 1.15, the retention engine's default)."""
    return 1.0 + 0.30 * max(0, min(100, int(intensity))) / 100
