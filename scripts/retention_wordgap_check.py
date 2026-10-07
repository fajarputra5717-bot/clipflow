"""Word-gap silence trim + 40 ms crossfade on one real clip (decision 2026-10-02).

Renders the same keep plan twice (crossfade 40 ms vs hard join with 8 ms micro-fades) and reports:
cuts, durations, audio-vs-video length, word timing at the words right after cuts (audio
cross-correlation), and two seam metrics:
  click score  max |dx| within +-3 ms of the seam / clip's 99th-percentile |dx| (<= ~1: no click)
  level dip    quietest 5 ms RMS within +-25 ms of the seam vs the median 5 ms RMS over +-250 ms,
               in dB (near 0 = the music/game bed carries through; very negative = it drops out)

  docker run --rm --cpus=2 -e PYTHONPATH=/work -v "$PWD":/work -w /work \
    -v /data/final:/in:ro -v /tmp/retention-wordgap:/out \
    -v riftstorm_hf_cache:/cache/huggingface:ro -e HF_HOME=/cache/huggingface -e HF_HUB_OFFLINE=1 \
    --entrypoint python riftstorm-worker:latest scripts/retention_wordgap_check.py /out /in/8b974b8e-....mp4
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from retention_real_check import FPS, audio_offset, duration, ff, pcm, words_of  # same dir
from shared import retention as r


def probe_durs(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return {s["codec_type"]: float(s["duration"]) for s in json.loads(p.stdout)["streams"]}


def pcm48(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "48000",
                        "-f", "f32le", "-"], capture_output=True, check=True, timeout=300)
    return np.frombuffer(p.stdout, dtype=np.float32)


def seam_scores(path, seams):
    x = pcm48(path)
    dx = np.abs(np.diff(x))
    ref = float(np.percentile(dx, 99)) or 1e-9
    w = int(0.003 * 48000)
    clicks = [round(float(dx[max(0, int(t * 48000) - w):int(t * 48000) + w].max()) / ref, 2) for t in seams]
    win = int(0.005 * 48000)

    def rms_series(a, b):
        seg = x[max(0, a):b]
        n = len(seg) // win
        return np.sqrt((seg[:n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)

    dips = []
    for t in seams:
        c = int(t * 48000)
        near = rms_series(c - int(0.025 * 48000), c + int(0.025 * 48000))
        around = rms_series(c - int(0.25 * 48000), c + int(0.25 * 48000))
        dips.append(round(20 * float(np.log10(near.min() / np.median(around))), 1))
    return clicks, dips


def main():
    out, clip = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    src = out / "src.mp4"
    shutil.copyfile(clip, src)
    d0 = duration(src)
    words, lang = words_of(src)
    keep = r.plan_word_gap_keep(d0, words, fps=FPS)
    tm = r.TimeMap(keep)
    seams = [tm.to_output_clamped(s) for s, _ in keep[1:]]
    res = {"seams_out_s": [round(t, 3) for t in seams], "clip": clip.name, "lang": lang, "words": len(words), "trim_default": r.SILENCE_TRIM_DEFAULT,
           "gaps_>=0.6s": len(r.word_gap_silences(words)), "cuts": len(keep) - 1,
           "dur_before": round(d0, 2), "planned_after": round(tm.duration, 3)}
    a_src = pcm(src)
    for name, xf in (("crossfade_40ms", r.CUT_CROSSFADE), ("hard_join", 0.0)):
        dst = out / f"{name}.mp4"
        ff(r.trim_zoom_cmd(str(src), str(dst), keep=keep, crossfade=xf, source_duration=d0, threads=2).argv)
        ds = probe_durs(dst)
        a_out = pcm(dst)
        checks = []
        for s, _ in keep[1:4]:  # first word after each of the first 3 cuts
            w = next((w for w in words if w["start"] >= s - 1e-6), None)
            if not w:
                continue
            p = r.remap_words([w], tm)[0]["start"]
            seg_end = next(ke for ks, ke in keep if ks <= w["start"] < ke)
            off, corr = audio_offset(a_src, a_out, w["start"], w["end"], p, seg_end)
            checks.append({"word": w["word"], "src": round(w["start"], 2), "out": round(p, 2),
                           "offset_ms": None if off is None else round(off * 1000), "corr": round(corr, 2)})
        res[name] = {"video_s": round(ds["video"], 3), "audio_s": round(ds["audio"], 3),
                     "av_diff_ms": round((ds["audio"] - ds["video"]) * 1000),
                     "word_checks": checks}
        res[name]["click_score"], res[name]["level_dip_db"] = seam_scores(dst, seams)
        print(name, json.dumps(res[name], ensure_ascii=False), flush=True)
    (out / "wordgap.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    xf = res["crossfade_40ms"]
    ok = (res["cuts"] > 0 and abs(xf["video_s"] - tm.duration) <= 1 / FPS + 1e-3
          and abs(xf["av_diff_ms"]) <= 30
          and all(c["offset_ms"] is not None and abs(c["offset_ms"]) <= 25 for c in xf["word_checks"]))
    print(json.dumps({k: v for k, v in res.items() if not isinstance(v, dict)}, ensure_ascii=False))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
