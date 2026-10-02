"""Retention engine: pure builders for ffmpeg steps (no subprocess, no DB, no settings reads).

Three effects, in the order the editor render applies them (see the editor build notes):

  (a) silence trim   detect -> plan keep segments -> trim+concat (sample-accurate audio,
                     frame-snapped cuts so audio and video lengths agree exactly)
  (b) loudnorm       two-pass EBU R128 to -14 LUFS, then a true-peak limiter (always last)
  (c) punch-in zoom  smooth 1.0 -> 1.15 -> 1.0 at given timestamps (smoothstep, per-frame scale)

Word timings: every cut changes the timeline, so captions/karaoke must be re-timed with the
same keep segments that drove the cut. `TimeMap` / `remap_words()` do that; silence cuts never
remove part of a word (word spans + padding are protected), only explicit `forced_cuts`
(e.g. a filler word the user removed) may.

The caller (worker) owns settings, paths, run_command(timeout=...) and disk checks; every
builder here takes plain values and returns argv lists or filter strings.
"""

from __future__ import annotations

import json
import math
import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

# Defaults (the worker passes runtime settings; these only apply when it doesn't).
SILENCE_NOISE_DB = -35.0     # silencedetect threshold
SILENCE_MIN_GAP = 0.50       # only silences at least this long are cut (s)
SILENCE_PAD = 0.12           # speech kept on each side of a cut (s)
WORD_PAD = 0.05              # extra protection around Whisper word spans (s)
SEAM_FADE = 0.008            # audio micro-fade at each seam, avoids clicks (s)
LOUDNORM_I = -14.0           # integrated loudness target (LUFS)
LOUDNORM_TP = -1.0           # true-peak ceiling (dBTP)
LOUDNORM_LRA = 11.0          # loudness range target (LU)
SILENT_INPUT_LUFS = -70.0    # below this the input counts as silent: skip loudnorm
CODEC_HEADROOM_DB = 0.5      # limiter sits this far below TP: AAC encoding overshoots ~0.2-0.3 dB
MIN_WORD_DUR = 0.02          # Whisper emits zero-length words; keep them with this length
ZOOM_PEAK = 1.15
ZOOM_RAMP = 0.25             # ease in / ease out (s)
ZOOM_HOLD = 1.00             # time at full zoom (s)
ZOOM_MAX_WINDOWS = 40        # keeps the per-frame expression small

Segment = tuple[float, float]


@dataclass(frozen=True)
class FFmpegStep:
    name: str
    argv: list[str]


# --------------------------------------------------------------------------- helpers

def _f(x: float) -> str:
    """Compact, locale-free number for filter strings."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _merge(segments: Iterable[Segment], gap: float = 0.0) -> list[Segment]:
    out: list[list[float]] = []
    for s, e in sorted((float(a), float(b)) for a, b in segments if b > a):
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _subtract(base: Sequence[Segment], holes: Sequence[Segment]) -> list[Segment]:
    """base minus holes; both lists of (start, end)."""
    holes = _merge(holes)
    out: list[Segment] = []
    for s, e in base:
        cur = s
        for hs, he in holes:
            if he <= cur or hs >= e:
                continue
            if hs > cur:
                out.append((cur, hs))
            cur = max(cur, he)
            if cur >= e:
                break
        if cur < e:
            out.append((cur, e))
    return out


def encode_args(preset: str = "veryfast", crf: str | int = 20, audio_bitrate: str = "128k") -> list[str]:
    """Same output contract as worker renders (browser-safe mp4, R-10)."""
    return ["-c:v", "libx264", "-preset", str(preset), "-crf", str(crf),
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-movflags", "+faststart"]


# --------------------------------------------------------------------------- (a) silence trim

def silence_detect_cmd(src: str, *, noise_db: float = SILENCE_NOISE_DB,
                       min_gap: float = SILENCE_MIN_GAP) -> FFmpegStep:
    """Analysis pass; results arrive on stderr -> parse_silencedetect()."""
    return FFmpegStep("silence_detect", [
        "ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-sn", "-dn",
        "-af", f"silencedetect=noise={_f(noise_db)}dB:d={_f(min_gap)}", "-f", "null", "-"])


_SIL_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SIL_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_silencedetect(stderr: str, duration: float) -> list[Segment]:
    """(start, end) silences; an unterminated trailing silence runs to `duration`."""
    out: list[Segment] = []
    start: Optional[float] = None
    for line in stderr.splitlines():
        m = _SIL_START.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _SIL_END.search(line)
        if m and start is not None:
            out.append((start, min(float(m.group(1)), duration)))
            start = None
    if start is not None and start < duration:
        out.append((start, duration))
    return out


def relative_noise_db(integrated_lufs: Optional[float], *, below: float = 14.0,
                      lo: float = -50.0, hi: float = -25.0) -> float:
    """silencedetect threshold relative to the clip's loudness, for clips with a music/game bed
    that never reaches the absolute default (-35 dB). Clamped to [lo, hi]; default if unknown."""
    if integrated_lufs is None or not math.isfinite(integrated_lufs):
        return SILENCE_NOISE_DB
    return max(lo, min(hi, integrated_lufs - below))


def plan_keep_segments(duration: float, silences: Sequence[Segment] = (), *,
                       words: Sequence[dict] = (), forced_cuts: Sequence[Segment] = (),
                       min_gap: float = SILENCE_MIN_GAP, pad: float = SILENCE_PAD,
                       word_pad: float = WORD_PAD, fps: Optional[float] = None,
                       window: Optional[Segment] = None) -> list[Segment]:
    """Segments of the source to keep, in order.

    silences     auto cuts; shrunk by `pad` on both sides, never overlap a word span, and
                 only survive if still >= min_gap.
    forced_cuts  explicit removals (user-removed fillers etc.), applied as-is.
    window       optional (trim_start, trim_end) of the clip itself.
    fps          snap boundaries to the frame grid so video (frame-accurate) and audio
                 (sample-accurate) cut at identical times and stay in sync.
    """
    lo, hi = window if window else (0.0, duration)
    lo, hi = max(0.0, lo), min(duration, hi)
    protect = [(w["start"] - word_pad, w["end"] + word_pad) for w in words
               if w.get("end", 0) > w.get("start", 0)]
    cuts: list[Segment] = []
    for s, e in silences:
        s, e = s + pad, e - pad
        if e - s < min_gap:
            continue
        cuts += [c for c in _subtract([(s, e)], protect) if c[1] - c[0] >= min_gap]
    cuts += [(s, e) for s, e in forced_cuts if e > s]
    keep = _subtract([(lo, hi)], cuts)
    if fps:
        q = lambda t: round(t * fps) / fps
        keep = [(q(s), min(q(e), hi)) for s, e in keep]
        keep = [(s, e) for s, e in keep if e - s >= 1.0 / fps]
    return _merge(keep)


class TimeMap:
    """Source time <-> output time for a list of keep segments (sorted, disjoint)."""

    def __init__(self, keep: Sequence[Segment]):
        self.keep = list(keep)
        self._starts = [s for s, _ in self.keep]
        self._offsets: list[float] = []
        acc = 0.0
        for s, e in self.keep:
            self._offsets.append(acc)
            acc += e - s
        self.duration = acc

    def to_output(self, t: float) -> Optional[float]:
        """Output time of source time t, or None if t was cut."""
        i = bisect_right(self._starts, t) - 1
        if i < 0:
            return None
        s, e = self.keep[i]
        return self._offsets[i] + (t - s) if t < e or (t == e and i == len(self.keep) - 1) else None

    def to_output_clamped(self, t: float) -> float:
        """Like to_output, but a cut time snaps to the next kept moment (end of output if none)."""
        i = bisect_right(self._starts, t) - 1
        if i >= 0 and t < self.keep[i][1]:
            return self._offsets[i] + (t - self.keep[i][0])
        j = i + 1
        return self._offsets[j] if j < len(self.keep) else self.duration


def remap_words(words: Sequence[dict], keep: Sequence[Segment] | TimeMap) -> list[dict]:
    """Re-time Whisper words ({word,start,end,...}) onto the cut timeline.

    Words entirely inside a cut are dropped; a word that straddles a cut keeps only its
    kept part(s). Zero-length words (Whisper emits them) are kept with MIN_WORD_DUR.
    Extra keys are preserved, order is kept, start < end is guaranteed.
    """
    tm = keep if isinstance(keep, TimeMap) else TimeMap(keep)
    out = []
    for w in words:
        s, e = float(w["start"]), float(w["end"])
        parts = [(max(s, ks), min(e, ke)) for ks, ke in tm.keep
                 if (ks < e and ke > s) or (s == e and ks <= s < ke)]
        if not parts:
            continue
        ns = tm.to_output_clamped(parts[0][0])
        ne = tm.to_output_clamped(parts[-1][0]) + (parts[-1][1] - parts[-1][0])
        if ne - ns < MIN_WORD_DUR:  # zero-length Whisper word that was kept: give it a sliver
            ne = min(ns + MIN_WORD_DUR, tm.duration)
            if ne <= ns:
                continue
        out.append({**w, "start": round(ns, 3), "end": round(ne, 3)})
    return out


def remap_times(times: Iterable[float], keep: Sequence[Segment] | TimeMap) -> list[float]:
    """Markers (zoom, hook, SFX) onto the cut timeline; cut markers move to the next kept moment."""
    tm = keep if isinstance(keep, TimeMap) else TimeMap(keep)
    return [round(tm.to_output_clamped(t), 3) for t in times]


def silence_trim_graph(keep: Sequence[Segment], *, v_in: str = "0:v", a_in: str = "0:a",
                       v_out: str = "vtrim", a_out: str = "atrim", fade: float = SEAM_FADE) -> str:
    """filter_complex chunk: trim/atrim each keep segment and concat (video + audio).

    Audio gets a few-ms fade at every seam (no clicks). Labels are without brackets.
    """
    n = len(keep)
    if n == 0:
        raise ValueError("nothing to keep")
    parts = [f"[{v_in}]split={n}" + "".join(f"[sv{i}]" for i in range(n)),
             f"[{a_in}]asplit={n}" + "".join(f"[sa{i}]" for i in range(n))]
    pairs = []
    for i, (s, e) in enumerate(keep):
        d = e - s
        fd = min(fade, d / 4)
        parts.append(f"[sv{i}]trim=start={_f(s)}:end={_f(e)},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[sa{i}]atrim=start={_f(s)}:end={_f(e)},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={_f(fd)},afade=t=out:st={_f(d - fd)}:d={_f(fd)}[a{i}]")
        pairs.append(f"[v{i}][a{i}]")
    parts.append("".join(pairs) + f"concat=n={n}:v=1:a=1[{v_out}][{a_out}]")
    return ";".join(parts)


# --------------------------------------------------------------------------- (c) punch-in zoom

def plan_zoom_windows(markers: Iterable[float], duration: float, *, ramp: float = ZOOM_RAMP,
                      hold: float = ZOOM_HOLD, max_windows: int = ZOOM_MAX_WINDOWS) -> list[Segment]:
    """(start, end) zoom windows on the OUTPUT timeline; overlapping/touching ones merge into a
    longer hold instead of dipping out and back in."""
    wins = [(m, min(duration, m + 2 * ramp + hold)) for m in sorted(set(markers)) if 0 <= m < duration]
    wins = [w for w in _merge(wins, gap=ramp) if w[1] - w[0] >= 2 * ramp]
    return wins[:max_windows]


def zoom_expr(windows: Sequence[Segment], *, peak: float = ZOOM_PEAK, ramp: float = ZOOM_RAMP) -> str:
    """Per-frame zoom factor z(t) as an ffmpeg expression (1.0 outside windows).

    Each window: u = min(clip((t-s)/R,0,1), clip((e-t)/R,0,1)); smoothstep u*u*(3-2u).
    Windows are disjoint, so the sum of envelopes equals their max. Registers: 0 = u, 1 = sum.
    """
    if not windows:
        return "1"
    r = _f(ramp)
    terms = ["st(1,0)"]
    for s, e in windows:
        terms.append(f"st(0,min(clip((t-{_f(s)})/{r},0,1),clip(({_f(e)}-t)/{r},0,1)))")
        terms.append("st(1,ld(1)+ld(0)*ld(0)*(3-2*ld(0)))")
    terms.append(f"1+{_f(peak - 1)}*ld(1)")
    return ";".join(terms)


def zoom_filter(windows: Sequence[Segment], *, width: int = 1080, height: int = 1920,
                peak: float = ZOOM_PEAK, ramp: float = ZOOM_RAMP,
                center: tuple[float, float] = (0.5, 0.5)) -> Optional[str]:
    """Filter chain for a width x height input: per-frame upscale by z(t), then a fixed-size crop
    around `center` (fractions). None when there is nothing to zoom.

    Scale (not zoompan): zoompan rounds x/y to integers at the source size and visibly jitters;
    here only the even-pixel rounding of the scaled size remains (<= 2 px at 1080 wide).
    """
    if not windows:
        return None
    z = zoom_expr(windows, peak=peak, ramp=ramp)
    cx, cy = center
    return (f"scale=w='trunc(iw*({z})/2)*2':h=-2:eval=frame:flags=bicubic,"
            f"crop={width}:{height}:'(iw-ow)*{_f(cx)}':'(ih-oh)*{_f(cy)}',setsar=1")


# --------------------------------------------------------------------------- (b) loudnorm

def loudnorm_measure_cmd(src: str, *, i: float = LOUDNORM_I, tp: float = LOUDNORM_TP,
                         lra: float = LOUDNORM_LRA) -> FFmpegStep:
    """Pass 1: measurement only; JSON arrives on stderr -> parse_loudnorm()."""
    return FFmpegStep("loudnorm_measure", [
        "ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-sn", "-dn",
        "-af", f"loudnorm=I={_f(i)}:TP={_f(tp)}:LRA={_f(lra)}:print_format=json", "-f", "null", "-"])


def parse_loudnorm(stderr: str) -> Optional[dict]:
    """Measured values from pass 1, as floats; None for silent/unmeasurable input."""
    start = stderr.rfind("{")
    end = stderr.find("}", start)
    if start < 0 or end < 0:
        return None
    try:
        raw = json.loads(stderr[start:end + 1])
        vals = {k: float(raw[k]) for k in
                ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (ValueError, KeyError):
        return None
    if not all(math.isfinite(v) for v in vals.values()) or vals["input_i"] < SILENT_INPUT_LUFS:
        return None
    return vals


def loudnorm_filter(measured: Optional[dict], *, i: float = LOUDNORM_I, tp: float = LOUDNORM_TP,
                    lra: float = LOUDNORM_LRA, out_rate: int = 48000,
                    codec_headroom_db: float = CODEC_HEADROOM_DB) -> str:
    """Pass 2 audio chain: linear loudnorm with pass-1 values -> true-peak limiter -> out_rate.

    loudnorm outputs 192 kHz; limiting there (4x oversampled) approximates a true-peak limiter,
    and its ceiling sits codec_headroom_db below TP because AAC encoding overshoots: measured on
    real clips, a -1.0 limiter came out at -0.7..-0.8 dBTP after encoding. With no measurement (silent input) only the
    limiter + resample run. Keep this chain LAST in the audio graph (after any SFX mix).
    """
    limit = _f(round(10 ** ((tp - codec_headroom_db) / 20), 4))
    # The trailing aformat is required: ffmpeg 5.1 loudnorm/alimiter leave the channel layout
    # unset and the encoder link then fails ("Cannot select channel layout"), mono and stereo.
    tail = (f"alimiter=limit={limit}:attack=1:release=50:level=0,aresample={out_rate},"
            "aformat=channel_layouts=mono|stereo")
    if not measured:
        return f"aresample=192000,{tail}"
    m = measured
    return (f"loudnorm=I={_f(i)}:TP={_f(tp)}:LRA={_f(lra)}"
            f":measured_I={_f(m['input_i'])}:measured_TP={_f(m['input_tp'])}"
            f":measured_LRA={_f(m['input_lra'])}:measured_thresh={_f(m['input_thresh'])}"
            f":offset={_f(m['target_offset'])}:linear=true:print_format=summary,{tail}")


def ebur128_measure_cmd(src: str) -> FFmpegStep:
    """Verification meter (BS.1770 integrated + true peak) for a finished file -> parse_ebur128().
    Use this, not loudnorm's own JSON, to check an output: loudnorm's pass-1 numbers read up to
    ~0.8 LU off on high-range content after a dynamic-mode pass."""
    return FFmpegStep("ebur128", ["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-sn", "-dn",
                                  "-af", "ebur128=peak=true", "-f", "null", "-"])


def parse_ebur128(stderr: str) -> Optional[dict]:
    """{'i': LUFS, 'tp': dBTP} from the ebur128 summary; None if absent."""
    tail = stderr[stderr.rfind("Summary:"):] if "Summary:" in stderr else ""
    mi = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", tail)
    mp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", tail)
    if not (mi and mp):
        return None
    return {"i": float(mi.group(1)), "tp": float(mp.group(1))}


def loudnorm_apply_cmd(src: str, dst: str, measured: Optional[dict], *, audio_bitrate: str = "128k",
                       **targets) -> FFmpegStep:
    """Pass 2 as a standalone step: video stream copied, audio normalised."""
    return FFmpegStep("loudnorm_apply", [
        "ffmpeg", "-hide_banner", "-nostats", "-y", "-i", src, "-map", "0:v?", "-map", "0:a",
        "-c:v", "copy", "-af", loudnorm_filter(measured, **targets),
        "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-movflags", "+faststart", dst])


# --------------------------------------------------------------------------- combined render

def trim_zoom_cmd(src: str, dst: str, *, keep: Sequence[Segment] = (),
                  zoom_windows: Sequence[Segment] = (), width: int = 1080, height: int = 1920,
                  peak: float = ZOOM_PEAK, ramp: float = ZOOM_RAMP, preset: str = "veryfast",
                  crf: str | int = 20, threads: Optional[int] = None) -> FFmpegStep:
    """One encode: silence trim (if keep) then zoom (windows on the OUTPUT timeline).

    Input must already be width x height (the vertical render). Loudnorm runs afterwards on
    the result (measure -> apply), because it must see the final, cut audio.
    """
    graph: list[str] = []
    v, a = "0:v", "0:a"
    if keep:
        graph.append(silence_trim_graph(keep))
        v, a = "vtrim", "atrim"
    zf = zoom_filter(zoom_windows, width=width, height=height, peak=peak, ramp=ramp)
    if zf:
        graph.append(f"[{v}]{zf}[vzoom]")
        v = "vzoom"
    argv = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", src]
    if threads:
        argv += ["-threads", str(threads)]
    if graph:
        argv += ["-filter_complex", ";".join(graph)]
    argv += ["-map", f"[{v}]" if graph and v != "0:v" else "0:v",
             "-map", f"[{a}]" if a != "0:a" else "0:a?"]
    argv += encode_args(preset, crf) + [dst]
    return FFmpegStep("trim_zoom", argv)
