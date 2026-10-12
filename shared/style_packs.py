"""Style packs (Auto Edit E5, lane-b): owner definitions 2026-10-12 (docs/tasks/auto-edit.md § E5).

A pack = defaults for one clip: caption preset + keyword colour, which moments get which effect + sound, density
(min seconds between effects), look, progress bar, Loud & punchy, zoom intensity. Applying a pack writes those
edit_spec keys and regenerates the plan with the pack's mapping; every value stays overridable per clip afterwards.
Campaign defaults: IME + Fandra → Gaming Hype, everything else (and no campaign) → Podcast Clean.
"""
from __future__ import annotations

from typing import Optional

# moment kind → effects to cycle through (effect, params); a kind not listed is not used by the pack.
# Kinds come from edit_director: hook, punchline, shock, laugh, reaction (vision), loud (audio peak), cut (seam).
PACKS: dict[str, dict] = {
    "gaming_hype": {
        "name": "Gaming Hype",
        "caption": {"preset": "hormozi", "keyword_color": "#30D158"},
        "map": {
            "hook": [("punch", {"sfx": "bass_hit"})],
            "shock": [("punch", {"sfx": "boom"})],
            "punchline": [("punch", {"sfx": "bass_hit"})],
            "reaction": [("punch", {})],
            "loud": [("shake", {"sfx": "boom"}), ("flash", {"sfx": "bass_hit"})],
            "cut": [("whip", {"sfx": "whoosh"})],
        },
        "min_gap": 3.0, "look": {"preset": "vivid_gaming"}, "progress": True, "loud": True, "zoom_intensity": 60,
    },
    "funny_meme": {
        "name": "Funny / Meme",
        "caption": {"preset": "pop", "keyword_color": None},
        "map": {
            "punchline": [("freeze", {"hold": 0.6, "sfx": "record_scratch"})],
            "laugh": [("emoji", {"emoji": "😂", "sfx": "ding"}), ("emoji", {"emoji": "😭", "sfx": "ding"}),
                      ("emoji", {"emoji": "💀", "sfx": "ding"})],        # "laugh" SFX: no CC0 recording yet → ding
            "shock": [("slowmo", {"dur": 1.2, "factor": 0.5})],          # fails
            "hook": [("punch", {"sfx": "ding"})],
            "reaction": [("emoji", {"emoji": "😂"})],
        },
        "min_gap": 3.0, "look": {"preset": "warm"}, "progress": False, "loud": False, "zoom_intensity": 50,
    },
    "drama_tension": {
        "name": "Drama / Tension",
        "caption": {"preset": "clean", "keyword_color": None},
        "map": {
            "hook": [("push", {})],
            "shock": [("push", {"sfx": "boom"})],                        # reveals: low boom
            "punchline": [("push", {"sfx": "boom"})],
            "reaction": [("push", {})],
        },
        "min_gap": 5.0, "look": {"preset": "moody", "vignette": True}, "progress": False, "loud": False,
        "zoom_intensity": 50,
    },
    "podcast_clean": {
        "name": "Podcast Clean",
        "caption": {"preset": "karaoke", "keyword_color": None},
        "map": {
            "hook": [("punch", {})],                                     # subtle zooms on emphasis only
            "punchline": [("punch", {})],
        },
        "min_gap": 6.0, "look": None, "progress": False, "loud": False, "zoom_intensity": 25,
    },
}
DEFAULT_PACK = "podcast_clean"
CAMPAIGN_PACKS = {"ime-roleplay": "gaming_hype", "fandra-octo": "gaming_hype"}


def pack_for_campaign(campaign: Optional[str]) -> str:
    return CAMPAIGN_PACKS.get(campaign or "", DEFAULT_PACK)


def resolve(spec: Optional[dict], campaign: Optional[str]) -> tuple[str, bool]:
    """(pack id, from_campaign): the clip's own choice (edit_spec.pack) or its campaign default."""
    own = (spec or {}).get("pack") if isinstance(spec, dict) else None
    if own in PACKS:
        return own, False
    return pack_for_campaign(campaign), True


def options() -> list[dict]:
    return [{"id": k, "name": v["name"], "min_gap": v["min_gap"]} for k, v in PACKS.items()]
