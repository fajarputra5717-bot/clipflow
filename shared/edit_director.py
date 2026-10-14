"""Edit director (Auto Edit E1, lane-b): a restrained per-clip edit plan from the clip's own signals.

Signals (all in clip-SOURCE seconds, the basis of zoom markers and cuts):
  transcript  utility AI labels hook / punchline / shock / laugh moments in the timed words
  vision      optional: 4–6 frames sampled at preview time, the same AI call labels reaction peaks
  audio       loud peaks in the timeline waveform (already cached per preview)
  cut         seams the user made (whip transitions arrive in E2)
plan() merges them into items {id, t, effect, params, reason, source, on} and applies the restraint rules,
measured in OUTPUT seconds (after cuts, via retention.TimeMap): ≥ MIN_GAP s between effects AND from the user's
own zoom markers, nothing under the hook title card (the first card seconds of the output), nothing in
removed/trimmed ranges, nothing in the last END_GUARD s. Pure functions only (frame extraction argv included); the AI call is the caller's
(routes_editor) via shared/ai/router.py, task "edit_moments" (TEXT_UTILITY_PROVIDER).
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from shared.retention import TimeMap

VERSION = 1
MIN_GAP = 3.0             # s between two effects ("max ~1 effect per 3 s")
END_GUARD = 0.5           # s: no effect starting this close to the end
START_GUARD = 0.5         # s: nor in the first half second of the output (QA 7fc6a5a Low: punch at 0.0)
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
PARAMS_FOR = {"emoji": {"emoji": "😂"}, "freeze": {"hold": 0.6}, "slowmo": {"dur": 1.2, "factor": 0.5}}
MOTION_EFFECTS = ("punch", "push", "zoom_out", "shake", "flash", "whip")    # zoom stage (source time, pre-captions)
TIME_EFFECTS = ("freeze", "slowmo")                                         # cut stage (post-captions, re-times)
EFFECTS = MOTION_EFFECTS + TIME_EFFECTS + ("emoji",)                        # what a plan item may be switched to
RENDERED_EFFECTS = set(MOTION_EFFECTS) | set(TIME_EFFECTS) | {"emoji"}      # E3: emoji pops render too
ARRIVES_IN: dict = {}
# E3 assets (worker/assets, licences in worker/assets/LICENSES.md): Noto Emoji PNGs (Apache 2.0) + in-house SFX (CC0).
EMOJI = {"😂": "1f602", "😭": "1f62d", "💀": "1f480", "🔥": "1f525", "😱": "1f631", "👀": "1f440", "🤯": "1f92f", "😎": "1f60e"}
SFX = ("whoosh", "boom", "bass_hit", "ding", "record_scratch", "laugh")   # 217: laugh = the user's own sound, else ding
EMOJI_DUR = 1.4           # s on screen (pop in, hold, fade)
# Higher wins when two candidates are closer than MIN_GAP. A seam the user cut on purpose outranks a vision
# guess and a loudness peak (QA 7fc6a5a Low: whips were never proposed next to another candidate).
PRIORITY = {"transcript": 3, "cut": 2.5, "vision": 2, "audio": 1}

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
    """Seams: the first kept moment after each removed range (its end), where the kept video jumps."""
    return sorted(round(float(b), 2) for _a, b in removed or [])


def _blocked(t: float, *, duration: float, removed, trim) -> Optional[str]:
    if t >= duration - END_GUARD:
        return "too close to the end"
    for a, b in removed or []:
        if a <= t < b:
            return "inside a cut"
    if trim and not (trim[0] <= t < trim[1]):
        return "trimmed off"
    return None


def plan(*, duration: float, moments: Sequence[dict] = (), loud: Sequence[float] = (),
         cuts: Sequence[float] = (), card_seconds: float = 0.0, removed=(), trim=None, keep=None,
         taken: Sequence[float] = (), min_gap: float = MIN_GAP, mapping: Optional[dict] = None) -> list[dict]:
    """Merge signals into restrained items, time-sorted (t stays in source seconds).
    keep = the clip's keep segments (None = uncut); card_seconds = hook title card length (0 = no card);
    taken = source times already holding an effect (the user's zoom markers): planned items keep min_gap
    from them too."""
    tm = TimeMap(keep) if keep else None
    out = (lambda t: tm.to_output_clamped(t)) if tm else (lambda t: t)
    out_end = tm.duration if tm else duration
    cands = []
    for m in moments:
        src = "vision" if m["kind"] == "reaction" else "transcript"
        cands.append((m["t"], m["kind"], src, m.get("text") or m["kind"]))
    cands += [(t, "loud", "audio", "loudness peak") for t in loud]
    cands += [(t, "cut", "cut", "cut seam") for t in cuts]
    # best first: priority, then earlier
    cands.sort(key=lambda c: (-PRIORITY[c[2]], c[0]))
    occupied = [out(float(t)) for t in taken]
    kept: list[dict] = []
    used: dict = {}
    for t, kind, src, text in cands:
        if mapping is not None and not mapping.get(kind):
            continue                                   # E5: the pack doesn't use this kind of moment
        if _blocked(t, duration=duration, removed=removed, trim=trim):
            continue
        o = out(t)
        if o < max(card_seconds, START_GUARD) or o >= out_end - END_GUARD:
            continue
        if any(abs(o - x) < min_gap for x in occupied):
            continue
        if mapping is not None:                        # E5: cycle through the pack's effects for this kind
            choices = mapping[kind]
            effect, extra = choices[used.get(kind, 0) % len(choices)]
            used[kind] = used.get(kind, 0) + 1
        else:
            effect, extra = EFFECT_FOR[kind], {}
        occupied.append(o)
        kept.append({"id": f"{effect}-{int(round(t * 100))}", "t": round(t, 2), "effect": effect,
                     "params": {**PARAMS_FOR.get(effect, {}), **extra}, "reason": f"{kind}: {text}"[:100],
                     "source": src, "on": True})
        if len(kept) >= MAX_ITEMS:
            break
    return sorted(kept, key=lambda k: k["t"])


def frame_times(duration: float, *, count: int = FRAME_COUNT, removed=(), trim=None) -> list[float]:
    """Evenly spread sample times (centres of count equal slices), skipping removed/trimmed spots."""
    out = []
    for i in range(count):
        t = round((i + 0.5) * duration / count, 2)
        if not _blocked(t, duration=duration + END_GUARD, removed=removed, trim=trim):
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


# ---- E2 render helpers (pure): what the worker's zoom stage and cut stage apply from the plan

def _on(director: Optional[dict], kinds) -> list[dict]:
    return [i for i in (director or {}).get("items") or [] if i.get("on") and i.get("effect") in kinds]


def motion_events(director: Optional[dict], removed=()) -> list[tuple]:
    """Plan items for retention.motion_filter: (kind, t) or ("whip", t, out_start). A whip at a cut's end (a seam)
    starts its outgoing half at the cut's START, so both halves meet across the cut."""
    out = []
    for i in _on(director, MOTION_EFFECTS):
        t = float(i["t"])
        if i["effect"] == "whip":
            a = next((float(x) for x, y in removed or [] if abs(float(y) - t) < 0.03), t)
            out.append(("whip", t, a))
        else:
            out.append((i["effect"], t))
    return out


def warps(director: Optional[dict]) -> list[tuple]:
    """Plan items for retention.warp_pieces: ("freeze", t, hold) | ("slowmo", t, dur, factor)."""
    out = []
    for i in _on(director, TIME_EFFECTS):
        p = {**PARAMS_FOR[i["effect"]], **(i.get("params") or {})}
        if i["effect"] == "freeze":
            out.append(("freeze", float(i["t"]), max(0.2, min(2.0, float(p["hold"])))))
        else:
            out.append(("slowmo", float(i["t"]), max(0.3, min(3.0, float(p["dur"]))),
                        max(0.5, min(1.0, float(p["factor"])))))
    return out


def keep_of(spec: Optional[dict], clip: float) -> list[tuple]:
    """Kept source segments from edit_spec.cuts (trim minus removed ranges); the whole clip when uncut."""
    cuts = (spec or {}).get("cuts") if isinstance(spec, dict) else None
    cuts = cuts if isinstance(cuts, dict) else {}
    a, b = cuts.get("trim") or [0.0, clip]
    keep = [(float(a), min(float(b), float(clip)))]
    for s, e in cuts.get("removed") or []:
        nxt = []
        for x, y in keep:
            if e <= x or s >= y:
                nxt.append((x, y))
            else:
                if s > x:
                    nxt.append((x, float(s)))
                if e < y:
                    nxt.append((float(e), y))
        keep = nxt
    return [(x, y) for x, y in keep if y > x]


def time_extra(director: Optional[dict], keep) -> float:
    """Seconds the time effects add to the output (freeze holds + slowed time), for the kept segments."""
    from shared import retention
    w = warps(director)
    if not w or not keep:
        return 0.0
    pieces = retention.warp_pieces(keep, w)
    return max(0.0, retention.pieces_output_seconds(pieces) - sum(float(b) - float(a) for a, b in keep))


# ---- E3 render helpers (pure)

def emoji_events(director: Optional[dict]) -> list[tuple]:
    """[(t, emoji codepoint (file name), side)] source seconds; consecutive pops alternate right/left so they don't stack."""
    out = []
    for n, i in enumerate(_on(director, ("emoji",))):
        ch = (i.get("params") or {}).get("emoji") or PARAMS_FOR["emoji"]["emoji"]
        if ch in EMOJI:
            out.append((float(i["t"]), EMOJI[ch], "right" if n % 2 == 0 else "left"))
    return out


def to_output(t: float, keep=None, pieces=None) -> Optional[float]:
    """Source seconds → output seconds through cuts (keep) and time effects (pieces); None if t was cut."""
    if pieces:
        acc = 0.0
        for a, b, sp, hold in pieces:
            if a <= t < b:
                return acc + (t - a) / sp
            if hold and abs(t - b) < 1e-6:          # a freeze at t: its sound starts when the frame freezes
                return acc + (b - a) / sp
            acc += (b - a) / sp + hold
        return None
    if keep:
        acc = 0.0
        for a, b in keep:
            if a <= t < b:
                return acc + (t - a)
            acc += b - a
        return None
    return t


def sfx_events(director: Optional[dict], keep=None, pieces=None) -> list[tuple]:
    """[(output seconds, sfx name)] for enabled items that carry params.sfx; cut ones dropped."""
    out = []
    for i in (director or {}).get("items") or []:
        name = (i.get("params") or {}).get("sfx")
        if not i.get("on") or name not in SFX:
            continue
        o = to_output(float(i["t"]), keep, pieces)
        if o is not None:
            out.append((round(o, 3), name))
    return sorted(out)
