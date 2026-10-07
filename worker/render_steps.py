"""Editor render steps (lane B, roadmap P4). Called from worker.py through one-line hooks marked
`# lane-b hook`; everything else lives here so worker.py stays Lane A's.

Hook title card (editor task 1): edit_spec.hook_title = {on, text, duration}. A white rounded card
with the hook text over the first 2/2.5/3 s, popping in with a small spring and fading out. It is
written as ASS events into the SAME .ass the render burns (preview and final use identical code,
only the canvas size differs), or into its own title-only .ass when burned-in captions are off.
Placement: horizontally centred, below the watermark (never covers it: campaign placement rule)
and below the platform top-UI band (16 %).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from shared import edit_spec as edit_specs

CARD_FONT = "Montserrat ExtraBold"          # selected by name, ASS Bold=0 (R-19: no faux bold)
FONT_FILES = ("/usr/share/fonts/truetype/clipflow/montserrat/Montserrat[wght].ttf",
              str(Path(__file__).resolve().parent / "fonts" / "montserrat" / "Montserrat[wght].ttf"))
TOP_UI_FRAC = 0.16                            # platform top UI (same floor as the watermark, 078)
GAP_FRAC = 0.02                               # space between the watermark and the card
FALLBACK_TOP_FRAC = 0.36                      # no watermark rect known: clear a 16–34 % band
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U0000200D]")


def clip_title(candidate: dict) -> str:
    """Default card text = the clip's title as the UI shows it."""
    return (candidate.get("manual_title") or candidate.get("title") or candidate.get("ai_title") or "").strip()


def card_text(candidate: dict) -> Optional[str]:
    spec = edit_specs.hook_title_of(candidate.get("edit_spec"))
    if not spec or not spec.get("on"):
        return None
    text = (spec.get("text") or clip_title(candidate)).strip()
    text = re.sub(r"\s+", " ", _EMOJI.sub("", text)).strip()  # libass can't draw emoji
    return text or None


# --------------------------------------------------------------------------- measuring + layout

_font_cache: dict = {}


def _font(px: int):
    if px in _font_cache:
        return _font_cache[px]
    f = None
    try:
        from PIL import ImageFont
        for path in FONT_FILES:
            if Path(path).exists():
                f = ImageFont.truetype(path, px)
                try:
                    f.set_variation_by_name("ExtraBold")
                except Exception:
                    pass
                break
    except Exception:
        f = None
    _font_cache[px] = f
    return f


def text_width(text: str, px: int) -> float:
    f = _font(px)
    if f is None:
        return len(text) * px * 0.62           # Montserrat ExtraBold average advance
    return f.getlength(text)


def wrap(text: str, px: int, max_w: float, max_lines: int = 3) -> list[str]:
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if cur and text_width(trial, px) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:                  # never more than 3 lines: ellipsis on the last
        lines = lines[:max_lines]
        while lines[-1] and text_width(lines[-1] + "…", px) > max_w:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    return lines


def card_layout(text: str, width: int, height: int, avoid: Optional[dict] = None) -> dict:
    """Card geometry on a width x height canvas (same proportions for preview and final)."""
    fs = max(12, round(height * 0.030))
    pad_x, pad_y = round(width * 0.04), round(fs * 0.55)
    lines = wrap(text, fs, width * 0.80 - 2 * pad_x)
    line_h = round(fs * 1.18)
    tw = max(text_width(l, fs) for l in lines)
    bw = round(tw + 2 * pad_x)
    bh = round(len(lines) * line_h + 2 * pad_y)
    if avoid and avoid.get("h"):
        top = max(TOP_UI_FRAC * height, avoid["y"] + avoid["h"] + GAP_FRAC * height)
    else:
        top = FALLBACK_TOP_FRAC * height
    return {"fs": fs, "lines": lines, "w": bw, "h": bh, "r": round(min(bh / 2, width * 0.028)),
            "cx": round(width / 2), "cy": round(top + bh / 2), "top": round(top)}


# --------------------------------------------------------------------------- ASS

def _rounded_rect(w: int, h: int, r: int) -> str:
    k = round(r * 0.45)                         # bezier handle: close to a circular corner
    return (f"m {r} 0 l {w - r} 0 b {w - k} 0 {w} {k} {w} {r} l {w} {h - r} b {w} {h - k} {w - k} {h} {w - r} {h} "
            f"l {r} {h} b {k} {h} 0 {h - k} 0 {h - r} l 0 {r} b 0 {k} {k} 0 {r} 0")


def _ts(t: float) -> str:
    cs = max(0, round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "⧵").replace("{", "(").replace("}", ")")


POP = r"\fscx90\fscy90\t(0,200,0.6,\fscx103\fscy103)\t(200,330,\fscx100\fscy100)\fad(160,220)"


def card_events(text: str, width: int, height: int, duration: float, avoid: Optional[dict] = None,
                start: float = 0.0) -> list[str]:
    """Dialogue lines (shadow, card, text) on layers above the captions, from `start` to `duration`
    (both in the render's source time)."""
    g = card_layout(text, width, height, avoid)
    end = _ts(duration)
    t0 = _ts(start)
    pos = rf"\an5\pos({g['cx']},{g['cy']})"
    shadow_pos = rf"\an5\pos({g['cx']},{g['cy'] + round(height * 0.004)})"
    shape = _rounded_rect(g["w"], g["h"], g["r"])
    text_ass = r"\N".join(_esc(l) for l in g["lines"])
    return [
        f"Dialogue: 20,{t0},{end},HookCard,,0,0,0,,{{{shadow_pos}{POP}\\p1\\bord0\\shad0\\1c&H000000&\\1a&HA0&\\blur{max(2, round(height * 0.006))}}}{shape}",
        f"Dialogue: 21,{t0},{end},HookCard,,0,0,0,,{{{pos}{POP}\\p1\\bord0\\shad0\\1c&HFFFFFF&\\1a&H00&}}{shape}",
        f"Dialogue: 22,{t0},{end},HookCard,,0,0,0,,{{{pos}{POP}\\fs{g['fs']}\\q2}}{text_ass}",
    ]


STYLE = ("Style: HookCard,{font},{fs},&H00111111,&H00111111,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1")


def _header(width: int, height: int) -> str:
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
        "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,"
        "MarginV,Encoding", "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text", ""])


def card_window(dur: float, keep) -> tuple[float, float]:
    """(start, end) in SOURCE time so the card fills `dur` seconds of the OUTPUT after cuts:
    starts at the first kept moment and ends where the cut timeline reaches `dur`."""
    if not keep:
        return 0.0, dur
    left = dur
    for a, b in keep:
        if b - a >= left:
            return keep[0][0], a + left
        left -= b - a
    return keep[0][0], keep[-1][1]


def add_title_card(ass_path, candidate: dict, *, size: tuple[int, int], clip_duration: float,
                   avoid: Optional[dict] = None, out_dir=None, log=print):
    """The worker hook. Returns the .ass path the render should burn: unchanged when the card is off,
    the same file with the card appended, or (captions off) a new title-only .ass named with the
    candidate id (orphan sweep rule)."""
    try:
        text = card_text(candidate)
        if not text:
            return ass_path
        width, height = size
        spec = edit_specs.hook_title_of(candidate.get("edit_spec"))
        dur = min(float(spec.get("duration") or edit_specs.HOOK_TITLE_DEFAULT_DURATION), float(clip_duration))
        t0, t1 = card_window(dur, cut_plan(candidate, clip_duration))
        fs = max(12, round(height * 0.030))
        if ass_path and Path(ass_path).exists():
            path = Path(ass_path)
            body = path.read_text(encoding="utf-8")
        else:
            path = Path(out_dir or "/tmp") / f"{candidate['id']}.title.ass"
            body = _header(width, height)
        style = STYLE.format(font=CARD_FONT, fs=fs)
        # style goes right after the Format line of [V4+ Styles]; events at the end
        body = re.sub(r"(\[V4\+ Styles\]\s*\nFormat:[^\n]*\n)", lambda m: m.group(1) + style + "\n", body, count=1)
        body = body.rstrip("\n") + "\n" + "\n".join(card_events(text, width, height, t1, avoid, start=t0)) + "\n"
        path.write_text(body, encoding="utf-8")
        log(f"Hook title card: {dur:.1f} s, {len(text)} chars, canvas {width}x{height}")
        return str(path)
    except Exception as e:  # never break a render over the card
        log(f"WARNING: hook title card skipped: {e}")
        return ass_path


# --------------------------------------------------------------------------- cuts (task 3)

CUT_FPS_DEFAULT = 30.0


def cut_plan(candidate: dict, clip_duration: float, fps: Optional[float] = None):
    """Keep segments (source seconds) from edit_spec.cuts, frame-snapped; None = no cuts."""
    from shared import retention
    cuts = edit_specs.cuts_of(candidate.get("edit_spec"))
    if not cuts:
        return None
    trim = cuts.get("trim") or [0.0, float(clip_duration)]
    keep = retention.plan_keep_segments(float(clip_duration), forced_cuts=[tuple(r) for r in cuts.get("removed") or []],
                                        window=(float(trim[0]), float(trim[1])), fps=fps or CUT_FPS_DEFAULT)
    full = [(0.0, float(clip_duration))]
    return None if not keep or keep == full else keep


def burn_segments(segments, candidate: dict, clip_duration: float):
    """Caption segments to BURN when the clip has cuts (QA 3597000/8f361a3 HIGH): words that are cut or
    outside the trim are removed from their lines (a line spanning a cut used to keep its full text on
    screen), each line's text is rebuilt from its remaining words, empty lines are dropped. Kept words
    keep their SOURCE timings: the cut pass (apply_cuts) maps captions and video onto the output timeline
    together, so karaoke stays in sync. A word counts as cut when more than half of it is removed.
    Unchanged when there are no cuts. The editor timeline keeps the full word list (write_timeline gets
    the unfiltered segments)."""
    keep = cut_plan(candidate, clip_duration)
    if not keep:
        return segments

    def kept_share(a, b):
        if b <= a:
            return 1.0 if any(x <= a < y for x, y in keep) else 0.0
        return sum(max(0.0, min(b, y) - max(a, x)) for x, y in keep) / (b - a)

    out = []
    for seg in segments or []:
        words = seg.get("words") or []
        if not words:
            mid = (float(seg.get("start", 0)) + float(seg.get("end", 0))) / 2
            if kept_share(mid, mid) > 0:
                out.append(seg)
            continue
        kept = [w for w in words if kept_share(float(w["start"]), float(w["end"])) > 0.5]
        if not kept:
            continue
        if len(kept) == len(words):
            out.append(seg)
            continue
        first_kept, last_kept = kept[0] is words[0], kept[-1] is words[-1]
        out.append({**seg, "words": kept,
                    "text": " ".join(str(w.get("word") or "").strip() for w in kept).strip(),
                    "start": seg.get("start") if first_kept else kept[0]["start"],
                    "end": seg.get("end") if last_kept else kept[-1]["end"]})
    return out


def _probe_fps(path) -> Optional[float]:
    import subprocess
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=avg_frame_rate", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        num, den = out.split("/")
        return float(num) / float(den) if float(den) else None
    except Exception:
        return None


def apply_cuts(path, candidate: dict, clip_duration: float, *, preset, crf, run, timeout=None, log=print):
    """After render_vertical (captions + card already burned, so karaoke is cut WITH the video): trim +
    remove the edit_spec.cuts ranges in place, 40 ms audio crossfade at each seam
    (retention.silence_trim_graph). Goes through the worker's run_command (cancel + watchdog).
    Returns the output duration, or None when the clip has no cuts. Loudnorm runs after this."""
    from shared import retention
    keep = cut_plan(candidate, clip_duration, _probe_fps(path))
    if not keep:
        return None
    tmp = Path(str(path) + ".cut.mp4")
    graph = retention.silence_trim_graph(keep, crossfade=retention.CUT_CROSSFADE, duration=float(clip_duration))
    run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(path), "-filter_complex", graph,
         "-map", "[vtrim]", "-map", "[atrim]", *retention.encode_args(preset, crf), str(tmp)], timeout=timeout)
    tmp.replace(path)
    out = sum(b - a for a, b in keep)
    log(f"Cuts: {len(keep)} segments, {clip_duration:.1f} s -> {out:.1f} s")
    return out


# --------------------------------------------------------------------------- zoom (task 4)

_render_ctx: dict = {}


def begin_render(candidate: dict, clip_duration: float) -> None:
    """Hook right before render_vertical() in preview + final: what zoom_stage() may use. One-shot
    (consumed by the next zoom_stage), so other render_vertical callers never pick up a stale clip."""
    _render_ctx.clear()
    _render_ctx.update(candidate=candidate, duration=float(clip_duration))


def zoom_stage(filters: list, last: str, width: int, height: int, log=print) -> str:
    """Hook inside render_vertical() right after the layout: append the punch-in zoom (retention.py,
    smooth per-frame scale + fixed crop) to the filter graph BEFORE the watermark and captions, so text
    never zooms. Times are clip-relative source seconds (render_vertical input-seeks to the clip start),
    the same basis as the editor markers; cuts happen after the render. Returns the new last label."""
    from shared import retention
    ctx = dict(_render_ctx)
    _render_ctx.clear()
    cand = ctx.get("candidate")
    if not cand:
        return last
    z = edit_specs.zoom_of(cand.get("edit_spec"))
    if not z or not z.get("on", True) or not z.get("markers"):
        return last
    peak = edit_specs.zoom_peak(z.get("intensity", edit_specs.ZOOM_DEFAULT_INTENSITY))
    if peak <= 1.0:
        return last
    wins = retention.plan_zoom_windows(z["markers"], ctx["duration"])
    zf = retention.zoom_filter(wins, width=width, height=height, peak=peak)
    if not zf:
        return last
    filters.append(f"[{last}]{zf}[zoomed];")
    log(f"Zoom: {len(wins)} punch-in(s), peak {peak:.2f}, canvas {width}x{height}")
    return "zoomed"


# --------------------------------------------------------------------------- timeline (task 2)

def write_timeline(preview_path, segments, duration, candidate, previews_dir, *, source_path=None, start=None, log=print):
    """After a preview render: waveform peaks + word chips → previews/<cid>.timeline.json, in SOURCE
    time (decoded from the source clip window, so cut words stay visible and restorable) plus the
    keep segments this preview was cut with. Never fatal (the editor then shows chips only)."""
    from shared import timeline
    try:
        candidate_id = candidate["id"] if isinstance(candidate, dict) else candidate
        keep = cut_plan(candidate, duration, _probe_fps(preview_path)) if isinstance(candidate, dict) else None
        data = timeline.build(source_path or preview_path, segments, duration,
                              start=start if source_path else None, keep=keep)
        timeline.write_cache(timeline.cache_path(previews_dir, candidate_id), data, preview_path)
        log(f"Timeline: {len(data['words'])} words, {len(data['peaks'] or [])} peaks")
    except Exception as e:
        log(f"WARNING: timeline skipped: {e}")
