"""
Per-clip edits (editor redesign P1, 108+): clip_candidates.edit_spec JSONB.
NULL / missing key = today's behaviour (the job-level setting applies).

Keys so far:
  caption: {style, animation}  per-clip caption preset; overrides the job's
           subtitle_style style/animation (font/size stay job-level).

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


def normalize_patch(patch, styles, animations):
    """-> (merge dict, keys to remove). Unknown keys raise ValueError."""
    if not isinstance(patch, dict):
        raise ValueError("edit_spec must be an object")
    merge, remove = {}, []
    for key, value in patch.items():
        if key == "caption":
            value = normalize_caption(value, styles, animations)
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
