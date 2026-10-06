"""
Campaign rules (081): docs/campaigns/<slug>.rules.json (+ <slug>.md brief),
bind-mounted read-only at CAMPAIGNS_DIR in backend and worker. Re-read when a
file changes (mtime), so editing a rules file needs no rebuild.

jobs.campaign holds the slug; NULL = no campaign (today's behaviour).
"""

import json
import os
import re
from pathlib import Path

CAMPAIGNS_DIR = Path(os.getenv("CAMPAIGNS_DIR", "/app/campaigns"))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

_cache = {"key": None, "data": {}}


def _snapshot():
    try:
        files = sorted(CAMPAIGNS_DIR.glob("*.rules.json")) + sorted(CAMPAIGNS_DIR.glob("*.md"))
        return tuple((f.name, f.stat().st_mtime_ns) for f in files)
    except OSError:
        return ()


def _brief_pending(slug):
    """A brief counts as present once its .md holds the verbatim text."""
    try:
        text = (CAMPAIGNS_DIR / f"{slug}.md").read_text(encoding="utf-8")
    except OSError:
        return True
    return "--- BRIEF START ---" not in text


def load_all():
    """{slug: rules dict (+ 'slug', 'brief_pending')}, cached by mtime."""
    key = _snapshot()
    if key != _cache["key"]:
        data = {}
        for f in sorted(CAMPAIGNS_DIR.glob("*.rules.json")):
            slug = f.name[: -len(".rules.json")]
            if not SLUG_RE.match(slug):
                continue
            try:
                rules = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue  # a broken file mustn't take the others down
            rules["slug"] = slug
            rules["brief_pending"] = _brief_pending(slug)
            data[slug] = rules
        _cache.update(key=key, data=data)
    return _cache["data"]


def get(slug):
    return load_all().get(slug) if slug else None


def display_name(rules):
    return rules.get("name") or rules["slug"].replace("-", " ").title()


def hashtags(rules):
    """The campaign hashtags in their required ORDER (briefs fix the order,
    not the position; ClipFlow appends them at the end of the caption).
    `required_prefix` = the pre-2026-10-02 key name."""
    h = rules.get("hashtags") or {}
    return list(h.get("required_in_order") or h.get("required_prefix") or [])


def sources(rules):
    return [s for s in rules.get("sources") or [] if s.get("channel")]


def platforms(rules):
    return list(rules.get("platforms") or [])


# Rules about how a clip is posted/promoted, not what it shows: a transcript
# can't tell, so they're never part of the per-clip check (v2a's pre-post checks).
POSTING_RULES = frozenset({
    "no_fake_views", "no_reupload_without_editing", "no_copying_other_clippers",
    "stay_public",
})


def content_rules(rules, clip_checkable=False):
    """[{id, text}] from either key the fixtures use; clip_checkable drops
    the posting-behaviour rules."""
    out = list(rules.get("content_rules") or rules.get("forbidden") or [])
    if clip_checkable:
        out = [r for r in out if r.get("id") not in POSTING_RULES]
    return out


def title_examples(rules):
    content = rules.get("content") or {}
    title = rules.get("title") or {}
    return list(content.get("title_examples") or title.get("tone_examples") or [])


def title_language(rules):
    content = rules.get("content") or {}
    title = rules.get("title") or {}
    return content.get("title_language") or title.get("language") or "id"


def watermark(rules):
    """The preset to snapshot onto a job: asset id (or None) + asset name,
    width at 1080, opacity, centre y in %. None = the campaign sets none."""
    wm = rules.get("watermark") or {}
    preset = wm.get("preset") or {}
    if not wm:
        return None
    return {
        "required": bool(wm.get("required")),
        "asset_id": wm.get("asset_id"),
        "asset_name": wm.get("asset_name") or wm.get("asset"),
        "width": int(preset.get("width_px_at_1080") or 0) or None,
        "opacity": float(preset["opacity"]) if preset.get("opacity") is not None else None,
        "center_y_pct": float(preset["center_y_pct"]) if preset.get("center_y_pct") is not None else None,
    }


LAYOUTS = ("auto", "left", "right", "none")


def default_layout(rules):
    """117: the campaign's facecam layout for new jobs (rules "default_layout");
    "auto" when unset/unknown. IME = "none" (GTA RP streams have no facecam)."""
    v = str((rules or {}).get("default_layout") or "auto").strip().lower()
    return v if v in LAYOUTS else "auto"


def default_language(rules):
    """Analyze form pre-fill: the campaign's spoken language when its rules state
    one explicitly ("language", content.title_language or title.language), else
    None = keep Auto. Never the title_language() fallback "id"."""
    content = (rules or {}).get("content") or {}
    title = (rules or {}).get("title") or {}
    v = str((rules or {}).get("language") or content.get("title_language") or title.get("language") or "").strip().lower()
    return v if v in ("en", "id") else None


def summary(rules):
    """What the API returns per campaign (no payout internals)."""
    return {
        "slug": rules["slug"],
        "name": display_name(rules),
        "brief_pending": rules["brief_pending"],
        "default_layout": default_layout(rules),
        "default_language": default_language(rules),
        "platforms": platforms(rules),
        "sources": [s["channel"] for s in sources(rules)],
        "source_note": (rules.get("content") or {}).get("source"),
        "hashtags": hashtags(rules),
    }


_HASHTAG_RE = re.compile(r"(?<![\w&])#[\w]+", re.UNICODE)


def with_campaign_hashtags(text, rules):
    """081/093: campaign captions END with the campaign hashtags, in their exact
    order, nothing between them; any hashtag the model wrote is removed first.
    (Moved from main.py in 115 so the worker uses the same rule.)"""
    body = _HASHTAG_RE.sub("", text or "")
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r" +([,.!?;:])", r"\1", body)
    body = re.sub(r" *\n *", "\n", body).strip()
    return f"{body}\n\n{' '.join(hashtags(rules))}".strip()
