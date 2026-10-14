"""SFX library (217): per-user sound effects that replace the bundled ones per category.

Categories = the sound names the style packs and the Editor's plan use (edit_director.SFX); a user assigns at most one
of their own sounds to each. Render resolution (worker): assigned sound → bundled `<name>.wav` → `FALLBACK` (laugh has
no bundled recording, it falls back to ding). Uploads: content-sniffed (never the extension), probed with the demuxer
forced, 0.3–10 s, then trimmed + levelled to the bundled set (mean −14 dB, peak ≤ −3 dB) as 48 kHz WAV.
Freesound: CC0 + 0.5–4 s filtered server-side AND re-checked before a save; ranked by `rank()`. The API key is
FREESOUND_API_KEY from the environment, sent only as an Authorization header.
"""
from __future__ import annotations

import math
import re
from typing import Optional

CATEGORIES: dict[str, dict] = {   # order = the Settings list
    "laugh": {"label": "Laugh", "query": "laugh"},
    "ding": {"label": "Ding", "query": "ding"},
    "whoosh": {"label": "Whoosh", "query": "whoosh"},
    "boom": {"label": "Boom", "query": "boom impact"},
    "bass_hit": {"label": "Bass hit", "query": "bass hit"},
    "record_scratch": {"label": "Record scratch", "query": "record scratch"},
}
FALLBACK = {"laugh": "ding"}       # no bundled recording → this bundled sound until the user assigns one
BUNDLED = ("whoosh", "boom", "bass_hit", "ding", "record_scratch")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MIN_SECONDS, MAX_SECONDS = 0.3, 10.0
MAX_SOUNDS = 50
NAME_MAX = 60
TARGET_MEAN_DB, PEAK_CAP_DB = -14.0, -3.0      # bundled SFX: mean −12…−16 dB, peaks −3 dB
FORMATS = {"mp3": "mp3", "wav": "wav", "ogg": "ogg"}
CODECS = {"mp3", "vorbis", "opus", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_u8"}

FREESOUND_API = "https://freesound.org/apiv2"
FREESOUND_CC0 = "http://creativecommons.org/publicdomain/zero/1.0/"
FS_MIN, FS_MAX = 0.5, 4.0
FS_FETCH, FS_SHOW = 30, 8
FS_FIELDS = "id,name,username,license,duration,avg_rating,num_ratings,num_downloads,previews,url"
PREVIEW_HOST = re.compile(r"^https://cdn\.freesound\.org/previews/[0-9]+/[0-9A-Za-z_.-]+\.(mp3|ogg)$")
PREVIEW_MAX_BYTES = 3 * 1024 * 1024


def category_label(cat: Optional[str]) -> Optional[str]:
    return CATEGORIES[cat]["label"] if cat in CATEGORIES else None


def used_by(cat: str) -> list[str]:
    """Style packs that play this sound (Settings: 'Used by Funny / Meme')."""
    from shared import style_packs
    out = []
    for p in style_packs.PACKS.values():
        if any((params or {}).get("sfx") == cat for effects in p["map"].values() for _e, params in effects):
            out.append(p["name"])
    return out


def resolve_paths(assigned: dict, bundled_dir: str) -> dict:
    """{category: absolute path of the user's sound} → {sound name: path} for every category the mixer may meet."""
    base = bundled_dir.rstrip("/")
    out = {n: f"{base}/{n}.wav" for n in BUNDLED}
    for cat, fb in FALLBACK.items():
        out[cat] = out[fb]
    for cat, path in (assigned or {}).items():
        if cat in CATEGORIES and path:
            out[cat] = str(path)
    return out


def clean_name(raw, default: str = "Sound") -> str:
    s = re.sub(r"\s+", " ", str(raw or "")).strip()
    s = re.sub(r"\.(mp3|wav|ogg)$", "", s, flags=re.I).strip()
    return (s or default)[:NAME_MAX]


# --------------------------------------------------------------------------- upload checks

def sniff(head: bytes) -> Optional[str]:
    """The file's real container from its first bytes (the extension and the browser's type are ignored)."""
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def probe_cmd(path: str, fmt: str) -> list:
    """ffprobe with the demuxer forced to the sniffed format and only local file access (no playlists/URLs)."""
    return ["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-f", FORMATS[fmt], "-show_entries",
            "format=format_name,duration:stream=codec_type,codec_name,channels,duration:stream_disposition=attached_pic",
            "-of", "json", path]


def check_probe(data: dict) -> tuple[Optional[float], Optional[str]]:
    """(duration, None) or (None, user-facing reason)."""
    streams = (data or {}).get("streams") or []
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    video = [s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")]
    if not audio:
        return None, "No audio in this file"
    if video:
        return None, "Use an audio file (mp3, wav or ogg), not a video"
    if audio[0].get("codec_name") not in CODECS:
        return None, "Unsupported audio format (use mp3, wav or ogg)"
    try:
        dur = float((data.get("format") or {}).get("duration") or audio[0].get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if not math.isfinite(dur) or dur <= 0:
        return None, "Couldn't read the sound's length"
    if dur < MIN_SECONDS:
        return None, f"Too short ({dur:.1f} s; at least {MIN_SECONDS:g} s)"
    if dur > MAX_SECONDS:
        return None, f"Too long ({dur:.1f} s; max {MAX_SECONDS:g} s)"
    return dur, None


TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02"


def measure_cmd(path: str, fmt: str) -> list:
    return ["ffmpeg", "-hide_banner", "-nostats", "-protocol_whitelist", "file", "-f", FORMATS[fmt], "-i", path,
            "-vn", "-af", f"{TRIM},volumedetect", "-f", "null", "-"]


def parse_volumedetect(stderr: str) -> tuple[Optional[float], Optional[float]]:
    def grab(key):
        m = re.search(rf"{key}_volume:\s*(-?[0-9.]+|-inf) dB", stderr or "")
        return None if not m or m.group(1) == "-inf" else float(m.group(1))
    return grab("mean"), grab("max")


def gain_db(mean: Optional[float], peak: Optional[float]) -> float:
    """Gain that brings the sound to the bundled level without pushing its peak above the cap."""
    if mean is None or peak is None:
        return 0.0
    return round(max(-40.0, min(40.0, TARGET_MEAN_DB - mean, PEAK_CAP_DB - peak)), 2)


def convert_cmd(src: str, fmt: str, dst: str, gain: float, channels: int) -> list:
    return ["ffmpeg", "-hide_banner", "-nostats", "-y", "-protocol_whitelist", "file", "-f", FORMATS[fmt], "-i", src,
            "-vn", "-map_metadata", "-1", "-af", f"{TRIM},volume={gain}dB", "-ar", "48000",
            "-ac", str(max(1, min(2, int(channels or 1)))), "-c:a", "pcm_s16le", "-f", "wav", dst]


# --------------------------------------------------------------------------- Freesound

def search_params(query: str) -> dict:
    return {"query": clean_name(query, "sound")[:60], "page_size": FS_FETCH, "fields": FS_FIELDS,
            "filter": f'license:"Creative Commons 0" duration:[{FS_MIN} TO {FS_MAX}]', "sort": "score"}


def is_cc0(license_url) -> bool:
    return str(license_url or "").rstrip("/").replace("https://", "http://") == FREESOUND_CC0.rstrip("/")


def score(r: dict) -> float:
    """Bayesian rating (5 votes of 3.5 as the prior: one 5★ vote can't beat 200 votes of 4.6) + log downloads."""
    n = max(0, int(r.get("num_ratings") or 0))
    avg = float(r.get("avg_rating") or 0)
    rating = (n * avg + 5 * 3.5) / (n + 5)
    return rating + 0.5 * math.log10(1 + max(0, int(r.get("num_downloads") or 0)))


def preview_url(r: dict) -> Optional[str]:
    url = ((r.get("previews") or {}).get("preview-hq-mp3") or "")
    return url if PREVIEW_HOST.match(url) else None


def eligible(r: dict) -> bool:
    try:
        d = float(r.get("duration") or 0)
    except (TypeError, ValueError):
        return False
    return is_cc0(r.get("license")) and FS_MIN <= d <= FS_MAX and bool(preview_url(r)) and str(r.get("id", "")).isdigit()


def card(r: dict) -> dict:
    return {"id": int(r["id"]), "name": clean_name(r.get("name"))[:NAME_MAX], "author": str(r.get("username") or "")[:60],
            "duration": round(float(r["duration"]), 2), "license": "CC0", "url": str(r.get("url") or "")[:300],
            "rating": round(float(r.get("avg_rating") or 0), 1), "ratings": int(r.get("num_ratings") or 0),
            "downloads": int(r.get("num_downloads") or 0)}


def rank(results: list, show: int = FS_SHOW) -> list:
    """Freesound results → the top cards (CC0 + length re-checked here, never trusted from the filter alone)."""
    ok = [r for r in (results or []) if isinstance(r, dict) and eligible(r)]
    ok.sort(key=lambda r: (-score(r), -int(r.get("num_ratings") or 0), int(r["id"])))
    return [card(r) for r in ok[:show]]
