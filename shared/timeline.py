"""Editor timeline data (lane B, P4 task 2): waveform peaks + word chips for one clip.

Built by the worker right after a preview render (worker/render_steps.write_timeline, one
`# lane-b hook`) because only the worker has ffmpeg; cached next to the preview as
`<DATA_ROOT>/previews/<candidate_id>.timeline.json` (named with the candidate id: orphan-sweep rule).
The editor API serves the cache; without one (previews from before this change) it serves
`words_only()` (chips, no waveform).

Times are clip-relative seconds = the preview video's own timeline (0 … duration), the same
basis as clip_candidates.subtitle_segments (exactly what make_ass() burned).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from array import array
from pathlib import Path
from typing import Iterable, Optional

VERSION = 2                    # 2: source-time waveform + rendered `keep` (task 3)
PEAKS_PER_SECOND = 50          # one bar per 20 ms; 35 s clip → 1,750 values (~9 KB of JSON)
DECODE_RATE = 8000             # mono samples/s for peak extraction (plenty for a waveform)
FLOOR_DB = -48.0               # quietest level that still draws (dB full scale)
GAP_MIN = 0.30                 # pauses shorter than this are not shown as gap chips


def words_from_segments(segments) -> list[dict]:
    """Flat, time-sorted word list [{i, text, start, end}] from subtitle_segments."""
    words = []
    for seg in segments or []:
        for w in (seg or {}).get("words") or []:
            try:
                s, e = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            text = str(w.get("word") or "").strip()
            if text:
                words.append({"text": text, "start": round(s, 3), "end": round(max(e, s), 3)})
    words.sort(key=lambda w: w["start"])
    for i, w in enumerate(words):
        w["i"] = i
    return words


def gaps_between(words: list[dict], duration: Optional[float] = None, min_gap: float = GAP_MIN) -> list[dict]:
    """Pauses between consecutive words (and before the first / after the last) ≥ min_gap."""
    out, reach = [], 0.0
    for w in words:
        if w["start"] - reach >= min_gap:
            out.append({"start": round(reach, 3), "end": round(w["start"], 3)})
        reach = max(reach, w["end"])
    if duration is not None and duration - reach >= min_gap:
        out.append({"start": round(reach, 3), "end": round(float(duration), 3)})
    return out


def peaks_from_samples(samples: Iterable[float], sample_rate: int = DECODE_RATE,
                       per_second: int = PEAKS_PER_SECOND, floor_db: float = FLOOR_DB) -> list[float]:
    """Max |sample| per bucket, mapped from dB (floor_db … 0 dBFS) to 0…1, 2 decimals.
    dB scaling keeps quiet speech visible next to loud game audio."""
    samples = samples if isinstance(samples, (list, array)) else list(samples)
    step = max(1, sample_rate // per_second)
    out = []
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        m = max((abs(x) for x in chunk), default=0.0)
        db = 20 * math.log10(m) if m > 0 else floor_db
        out.append(round(min(1.0, max(0.0, (db - floor_db) / -floor_db)), 2))
    return out


def decode_cmd(media_path: str, sample_rate: int = DECODE_RATE, start: Optional[float] = None,
               duration: Optional[float] = None) -> list[str]:
    seek = (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{duration:.3f}"] if duration else [])
    return ["ffmpeg", "-v", "error", "-nostdin", *seek, "-i", str(media_path), "-vn", "-ac", "1",
            "-ar", str(sample_rate), "-f", "f32le", "-"]


def build(media_path, segments, duration: float, *, start: Optional[float] = None, keep=None,
          timeout: int = 120) -> dict:
    """Timeline dict in SOURCE time (the uncut clip window, so cut words stay visible): decodes
    media_path from `start` for `duration` once. keep = the segments the preview was rendered with
    (None = uncut); the editor maps the cut preview's time back to source time with it."""
    words = words_from_segments(segments)
    peaks: Optional[list] = None
    try:
        raw = subprocess.run(decode_cmd(media_path, start=start, duration=duration), capture_output=True,
                             check=True, timeout=timeout).stdout
        samples = array("f")
        samples.frombytes(raw[: len(raw) - len(raw) % 4])
        peaks = peaks_from_samples(samples)
    except (subprocess.SubprocessError, OSError):
        peaks = None  # chips still work without a waveform
    return {"version": VERSION, "duration": round(float(duration), 3), "rate": PEAKS_PER_SECOND,
            "peaks": peaks, "words": words, "gaps": gaps_between(words, duration),
            "keep": [[round(a, 3), round(b, 3)] for a, b in keep] if keep else None}


def words_only(segments, duration: float) -> dict:
    words = words_from_segments(segments)
    return {"version": VERSION, "duration": round(float(duration), 3), "rate": PEAKS_PER_SECOND,
            "peaks": None, "words": words, "gaps": gaps_between(words, duration), "keep": None}


def cache_path(previews_dir, candidate_id) -> Path:
    return Path(previews_dir) / f"{candidate_id}.timeline.json"


def write_cache(path, data: dict, preview_path=None) -> None:
    """Atomic write; records the preview's mtime so a newer preview invalidates it."""
    if preview_path and Path(preview_path).exists():
        data = {**data, "preview_mtime": round(Path(preview_path).stat().st_mtime, 3)}
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def read_cache(path, preview_path=None) -> Optional[dict]:
    """Cached timeline, or None if missing, unreadable, another version, or older than the preview."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("version") != VERSION:
        return None
    if preview_path and Path(preview_path).exists() and data.get("preview_mtime") is not None:
        if Path(preview_path).stat().st_mtime > float(data["preview_mtime"]) + 0.5:
            return None
    return data
