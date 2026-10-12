"""Edit director (Auto Edit E1, lane-b): a restrained per-clip edit plan from the clip's own signals.

Signals (all in clip-SOURCE seconds, the basis of zoom markers and cuts):
  transcript  utility AI labels hook / punchline / shock / laugh moments in the timed words
  vision      optional: 4–6 frames sampled at preview time, the same AI call labels reaction peaks
  audio       loud peaks in the timeline waveform (already cached per preview)
  cut         seams the user made (whip transitions arrive in E2)
plan() merges them into items {id, t, effect, params, reason, source, on} and applies the restraint rules:
≥ MIN_GAP s between effects, nothing inside the hook title card, nothing in removed/trimmed ranges, nothing in
the last END_GUARD s. Pure functions only (frame extraction argv included); the AI call is the caller's
(routes_editor) via shared/ai/router.py, task "edit_moments" (TEXT_UTILITY_PROVIDER).
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

VERSION = 1
MIN_GAP = 3.0             # s between two effects ("max ~1 effect per 3 s")
END_GUARD = 0.5           # s: no effect starting this close to the end
MAX_MOMENTS = 8
MAX_ITEMS = 12
FRAME_COUNT = 6
FRAME_WIDTH = 320
PEAK_WINDOW = 0.25        # s: local-max window for loudness peaks
PEAK_MIN_RATIO = 0.85     # a loudness peak must reach this share of the clip's max
MAX_LOUD_PEAKS = 6

KINDS = ("hook", "punchline", "shock", "laugh", "reaction")
# moment kind → effect. Packs (E5) will change this mapping; E1 renders only "punch".
EFFECT_FOR = {"hook": "punch", "punchline": "punch", "shock": "shake", "laugh": "emoji",
              "reaction": "punch", "loud": "shake", "cut": "whip"}
PARAMS_FOR = {"emoji": {"emoji": "😂"}}
RENDERED_EFFECTS = {"punch"}             # grows with E2–E4; others are planned but not rendered yet
ARRIVES_IN = {"shake": "E2", "whip": "E2", "emoji": "E3"}
# Higher wins when two candidates are closer than MIN_GAP.
PRIORITY = {"transcript": 3, "vision": 2, "audio": 1, "cut": 1}

MOMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "t": {"type": "number"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "text": {"type": "string"},
                },
                "required": ["t", "kind", "text"],
            },
        },
    },
    "required": ["moments"],
}


def _word_text(w: dict) -> str:
    return str(w.get("text") if "text" in w else w.get("word") or "").strip()


def transcript_lines(words: Sequence[dict], *, line_seconds: float = 3.0) -> list[str]:
    """Timed words grouped into short lines "[12.3] word word …" (start time of the first word)."""
    lines, cur, t0 = [], [], None
    for w in words:
        txt = _word_text(w)
        if not txt:
            continue
        s = float(w.get("start", 0))
        if t0 is None:
            t0 = s
        if cur and s - t0 >= line_seconds:
            lines.append(f"[{t0:.1f}] " + " ".join(cur))
            cur, t0 = [], s
        cur.append(txt)
    if cur:
        lines.append(f"[{t0:.1f}] " + " ".join(cur))
    return lines


def moments_prompt(words: Sequence[dict], duration: float, *, frame_times: Sequence[float] = (),
                   title: str = "") -> str:
    lines = transcript_lines(words)
    frames = ""
    if frame_times:
        frames = ("\n\nFrames from the clip are attached, in this order, taken at: "
                  + ", ".join(f"{t:.1f} s" for t in frame_times)
                  + ". If a frame shows a strong visible reaction (big face expression, sudden action), add a "
                  "moment of kind \"reaction\" at that frame's time.")
    return (
        "You are a short-form video editor. Pick the few moments in this clip that deserve an edit effect.\n"
        f"Clip length: {duration:.1f} s." + (f" Title: {title}." if title else "") + "\n"
        "Kinds: hook (the line that grabs attention), punchline (the payoff of a joke or story), shock "
        "(surprise, scream, sudden twist), laugh (people laughing), reaction (visible reaction in a frame).\n"
        f"Return at most {MAX_MOMENTS} moments, only strong ones; fewer is better than weak ones. "
        "t = the second the moment lands (use the transcript times), text = the words or a 3–6 word note.\n"
        "Transcript (start time in seconds, then the words):\n" + "\n".join(lines) + frames
    )


def parse_moments(data, duration: float) -> list[dict]:
    """Validated moments [{t, kind, text}] from the AI's JSON (bad rows dropped, times clamped/rounded)."""
    rows = data.get("moments") if isinstance(data, dict) else data
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or r.get("kind") not in KINDS:
            continue
        try:
            t = float(r.get("t"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(t) or t < 0 or t >= duration:
            continue
        out.append({"t": round(t, 2), "kind": r["kind"], "text": str(r.get("text") or "")[:80]})
    return out[:MAX_MOMENTS]


def loudness_peaks(peaks: Optional[Sequence[float]], rate: float, *, limit: int = MAX_LOUD_PEAKS) -> list[float]:
    """Times (s) of the loudest local maxima in a waveform peak list (one value per 1/rate s)."""
    if not peaks or not rate:
        return []
    vals = [abs(float(p)) for p in peaks]
    top = max(vals)
    if top <= 0:
        return []
    half = max(1, int(round(PEAK_WINDOW * rate)))
    hits = []
    for i, v in enumerate(vals):
        if v < PEAK_MIN_RATIO * top:
            continue
        win = vals[max(0, i - half): i + half + 1]
        if v >= max(win) and (not hits or i - hits[-1][0] > half):
            hits.append((i, v))
    hits.sort(key=lambda h: -h[1])
    return sorted(round(i / rate, 2) for i, _ in hits[:limit])


def cut_points(removed: Iterable[Sequence[float]]) -> list[float]:
    """Seams: where the kept video jumps (the start of each removed range)."""
    return sorted(round(float(a), 2) for a, _b in removed or [])


def _blocked(t: float, *, duration: float, card: Optional[tuple], removed, trim) -> Optional[str]:
    if t >= duration - END_GUARD:
        return "too close to the end"
    if card and card[0] <= t < card[1]:
        return "under the hook title card"
    for a, b in removed or []:
        if a <= t < b:
            return "inside a cut"
    if trim and not (trim[0] <= t < trim[1]):
        return "trimmed off"
    return None


def plan(*, duration: float, moments: Sequence[dict] = (), loud: Sequence[float] = (),
         cuts: Sequence[float] = (), hook_card: Optional[tuple] = None, removed=(), trim=None,
         min_gap: float = MIN_GAP) -> list[dict]:
    """Merge signals into restrained items, time-sorted. hook_card = (start, end) of the title card or None."""
    cands = []
    for m in moments:
        src = "vision" if m["kind"] == "reaction" else "transcript"
        cands.append((m["t"], m["kind"], src, m.get("text") or m["kind"]))
    cands += [(t, "loud", "audio", "loudness peak") for t in loud]
    cands += [(t, "cut", "cut", "cut seam") for t in cuts]
    # best first: priority, then earlier
    cands.sort(key=lambda c: (-PRIORITY[c[2]], c[0]))
    kept: list[dict] = []
    for t, kind, src, text in cands:
        if _blocked(t, duration=duration, card=hook_card, removed=removed, trim=trim):
            continue
        if any(abs(t - k["t"]) < min_gap for k in kept):
            continue
        effect = EFFECT_FOR[kind]
        kept.append({"id": f"{effect}-{int(round(t * 100))}", "t": round(t, 2), "effect": effect,
                     "params": dict(PARAMS_FOR.get(effect, {})), "reason": f"{kind}: {text}"[:100],
                     "source": src, "on": True})
        if len(kept) >= MAX_ITEMS:
            break
    return sorted(kept, key=lambda k: k["t"])


def frame_times(duration: float, *, count: int = FRAME_COUNT, removed=(), trim=None) -> list[float]:
    """Evenly spread sample times (centres of count equal slices), skipping removed/trimmed spots."""
    out = []
    for i in range(count):
        t = round((i + 0.5) * duration / count, 2)
        if not _blocked(t, duration=duration + END_GUARD, card=None, removed=removed, trim=trim):
            out.append(t)
    return out


def frame_cmd(src: str, start: float, t: float, dst: str, *, width: int = FRAME_WIDTH) -> list[str]:
    """One JPEG at source time start+t (input seek: fast), width px wide."""
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start + t:.3f}", "-i", src,
            "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "5", dst]


def punch_markers(director: Optional[dict]) -> list[float]:
    """Times of the plan's enabled punch items (rendered through the existing zoom stage)."""
    items = (director or {}).get("items") or []
    return [float(i["t"]) for i in items if i.get("on") and i.get("effect") == "punch"]
