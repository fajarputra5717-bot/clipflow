"""Run shared/retention.py on real clips: silence trim + 2 punch-ins + two-pass loudnorm.

Per clip it reports duration before/after, LUFS + true peak before/after (ebur128), and
spot-checks word timing against the AUDIO: for 3 words (first after a cut, middle, last) the
source audio of the word is cross-correlated with the output audio around the time TimeMap
predicts; the offset is the timing error. A second Whisper pass on the output is reported as a
coarse cross-check only (Whisper's own timestamps wander by ~100 ms). Silence threshold is
relative to the clip's loudness (relative_noise_db) because finals carry a music/game bed that
never reaches the -35 dB default; cuts at the default are reported too.
Read-only on the inputs; everything is written under OUT.

  docker run --rm --cpus=2 -e PYTHONPATH=/work -v "$PWD":/work -w /work \
    -v /data/final:/in:ro -v /tmp/retention-real:/out \
    -v riftstorm_hf_cache:/cache/huggingface:ro -e HF_HOME=/cache/huggingface -e HF_HUB_OFFLINE=1 \
    --entrypoint python riftstorm-worker:latest scripts/retention_real_check.py /out \
    /in/a.mp4 /in/b.mp4 +12:/in/c.mp4          # "+12:" = boost that clip 12 dB first (clipping test)

One ffmpeg / one Whisper at a time, 2 threads.
"""
import difflib
import numpy as np
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from shared import retention as r

FPS = 30
THREADS = "2"
MODEL = "medium"


def ff(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode:
        sys.exit(f"ffmpeg failed: {' '.join(argv)[:300]}\n{p.stderr[-1500:]}")
    return p.stderr


def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    return float(json.loads(p.stdout)["format"]["duration"])


def loudness(path):
    return r.parse_ebur128(ff(r.ebur128_measure_cmd(str(path)).argv))


SR = 16000


def pcm(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "-"], capture_output=True, check=True, timeout=300)
    return np.frombuffer(p.stdout, dtype=np.float32)


def audio_offset(src, out, s, e, p, seg_end, search=0.5):
    """Find the word's source audio [s, s+L] in the output around p; return (offset_s, corr)."""
    L = min(max(e - s, 0.35), 0.8, seg_end - s)
    tpl = src[int(s * SR):int((s + L) * SR)].astype(np.float64)
    lo = max(0, int((p - search) * SR))
    win = out[lo:int((p + search + L) * SR)].astype(np.float64)
    if len(tpl) < SR * 0.1 or len(win) <= len(tpl):
        return None, 0.0
    tpl = tpl - tpl.mean()
    num = np.correlate(win, tpl, mode="valid")
    c2 = np.concatenate([[0.0], np.cumsum(win * win)])
    c1 = np.concatenate([[0.0], np.cumsum(win)])
    n = len(tpl)
    var = (c2[n:] - c2[:-n]) - (c1[n:] - c1[:-n]) ** 2 / n
    corr = num / (np.sqrt(np.maximum(var, 1e-12)) * np.linalg.norm(tpl))
    k = int(np.argmax(corr))
    return (lo + k) / SR - p, float(corr[k])


_model = None


def words_of(path):
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=int(THREADS))
    segs, info = _model.transcribe(str(path), word_timestamps=True)
    return [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segs for w in (s.words or [])], info.language


def norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def whisper_check(predicted, heard, keep):
    """Align the two word lists by text; pick 3 matched words: first after the first cut, middle, last."""
    a, b = [norm(w["word"]) for w in predicted], [norm(w["word"]) for w in heard]
    pairs = []
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        pairs += [(predicted[blk.a + k], heard[blk.b + k]) for k in range(blk.size) if a[blk.a + k]]
    if not pairs:
        return [], 0, 0
    first_cut_out = keep[0][1] - keep[0][0] if len(keep) > 1 else 0
    after_cut = next((p for p in pairs if p[0]["start"] >= first_cut_out), pairs[0])
    picks = [after_cut, pairs[len(pairs) // 2], pairs[-1]]
    deltas = [abs(p["start"] - h["start"]) for p, h in pairs]
    med = sorted(deltas)[len(deltas) // 2]
    return [(p["word"], p["start"], h["start"]) for p, h in picks], med, len(pairs)


def run_clip(spec, out_root):
    boost = 0
    if spec.startswith("+") and ":" in spec:
        boost, spec = int(spec[1:spec.index(":")]), spec[spec.index(":") + 1:]
    src_in = Path(spec)
    work = out_root / src_in.stem[:8]
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src.mp4"
    if boost:  # deliberately clip: +N dB with no limiting
        ff(["ffmpeg", "-hide_banner", "-y", "-i", str(src_in), "-c:v", "copy", "-af", f"volume={boost}dB",
            "-c:a", "aac", "-b:a", "192k", "-threads", THREADS, str(src)])
    else:
        shutil.copyfile(src_in, src)

    d0, l0 = duration(src), loudness(src)
    words, lang = words_of(src)

    default_cuts = len(r.plan_keep_segments(
        d0, r.parse_silencedetect(ff(r.silence_detect_cmd(str(src)).argv), d0), words=words, fps=FPS)) - 1
    noise = r.relative_noise_db(l0 and l0["i"])
    sil = r.parse_silencedetect(ff(r.silence_detect_cmd(str(src), noise_db=noise).argv), d0)
    keep = r.plan_keep_segments(d0, sil, words=words, fps=FPS)
    tm = r.TimeMap(keep)
    wins = r.plan_zoom_windows(r.remap_times([d0 * 0.25, d0 * 0.6], tm), tm.duration)
    trimmed = work / "trim_zoom.mp4"
    ff(r.trim_zoom_cmd(str(src), str(trimmed), keep=keep, zoom_windows=wins, threads=int(THREADS)).argv)

    m = r.parse_loudnorm(ff(r.loudnorm_measure_cmd(str(trimmed)).argv))
    final = work / "final.mp4"
    ff(r.loudnorm_apply_cmd(str(trimmed), str(final), m).argv)
    no_lim = None
    if boost:  # same pass 2 without our limiter: shows what the limiter catches
        nl = work / "no_limiter.m4a"
        chain = re.sub(r",alimiter=[^,]+", "", r.loudnorm_filter(m))
        ff(["ffmpeg", "-hide_banner", "-y", "-i", str(trimmed), "-vn", "-af", chain, "-c:a", "aac",
            "-b:a", "128k", str(nl)])
        no_lim = loudness(nl)
        # pass-2 peak before the limiter, at 192 kHz
        pre = ff(["ffmpeg", "-hide_banner", "-nostats", "-i", str(trimmed), "-vn", "-af",
                  r.loudnorm_filter(m).split(",alimiter")[0] + ",ebur128=peak=true", "-f", "null", "-"])
        no_lim = {"encoded": no_lim, "pcm_192k": r.parse_ebur128(pre)}
    d1, l1 = duration(final), loudness(final)

    predicted = r.remap_words(words, tm)
    heard, _ = words_of(final)
    _, med, matched = whisper_check(predicted, heard, keep)

    # audio spot-checks: words with a usable length, first after the first cut, middle, last
    a_src, a_out = pcm(src), pcm(final)
    usable = [(w, pw) for w, pw in zip(words, predicted) if w["end"] - w["start"] >= 0.15] \
        if len(predicted) == len(words) else []
    if not usable:  # some words were cut: pair by remapping each source word on its own
        usable = [(w, r.remap_words([w], tm)[0]) for w in words
                  if w["end"] - w["start"] >= 0.15 and r.remap_words([w], tm)]
    first_cut = keep[0][1] if len(keep) > 1 else 0.0
    after = next((u for u in usable if u[0]["start"] >= first_cut), usable[0])
    checks = []
    for w, pw in (after, usable[len(usable) // 2], usable[-1]):
        seg_end = next(ke for ks, ke in keep if ks <= w["start"] < ke) if any(
            ks <= w["start"] < ke for ks, ke in keep) else w["end"]
        off, corr = audio_offset(a_src, a_out, w["start"], w["end"], pw["start"], seg_end)
        checks.append({"word": w["word"], "src_t": round(w["start"], 2), "predicted": round(pw["start"], 2),
                       "audio_found": None if off is None else round(pw["start"] + off, 3),
                       "offset_ms": None if off is None else round(off * 1000), "corr": round(corr, 2)})
    return {
        "clip": src_in.name, "boost_db": boost, "lang": lang,
        "dur_before": round(d0, 2), "dur_after": round(d1, 2), "planned_after": round(tm.duration, 2),
        "noise_db": noise, "cuts_at_default_-35dB": default_cuts, "cuts": len(keep) - 1,
        "removed_s": round(d0 - tm.duration, 2), "zoom_windows": wins,
        "lufs_before": l0 and l0["i"], "tp_before": l0 and l0["tp"],
        "lufs_after": l1 and l1["i"], "tp_after": l1 and l1["tp"],
        "without_limiter": no_lim,
        "words_src": len(words), "words_remapped": len(predicted), "words_heard": len(heard),
        "whisper_matched": matched, "whisper_median_abs_delta_s": round(med, 3),
        "audio_spot_checks": checks,
    }


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in sys.argv[2:]:
        res = run_clip(spec, out)
        results.append(res)
        print(json.dumps(res, ensure_ascii=False), flush=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    bad = [x["clip"] for x in results
           if not (x["lufs_after"] and abs(x["lufs_after"] + 14) <= 1 and x["tp_after"] <= -1.0
                   and all(c["offset_ms"] is not None and abs(c["offset_ms"]) <= 40
                           for c in x["audio_spot_checks"]))]
    print("ALL WITHIN TARGET" if not bad else f"OUT OF TARGET: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
