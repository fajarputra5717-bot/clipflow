"""Real-ffmpeg smoke test for shared/retention.py on a synthetic 1080x1920 clip.

Runs inside the worker image without touching containers or /data:
  docker run --rm --cpus=2 -v "$PWD":/work -w /work --entrypoint python \
    riftstorm-worker:latest scripts/retention_smoke.py /work/.retention-smoke
One ffmpeg at a time, 2 threads. Exit code 0 = all checks passed.
"""
import json
import subprocess
import sys
from pathlib import Path

from shared import retention as r

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/retention-smoke")
OUT.mkdir(parents=True, exist_ok=True)
FPS, DUR = 30, 10.0
SPEECH = [(0.0, 2.0), (3.5, 6.0), (7.5, 10.0)]          # tone bursts; gaps are silence
WORDS = [{"word": f"w{i}", "start": s + 0.2, "end": s + 0.6} for i, (s, _) in enumerate(SPEECH)]
fails = []


def run(argv):
    p = subprocess.run(argv + (["-threads", "2"] if "-f" in argv and argv[-1] == "-" else []),
                       capture_output=True, text=True, timeout=300)
    if p.returncode:
        sys.exit(f"ffmpeg failed: {' '.join(argv)[:300]}\n{p.stderr[-1500:]}")
    return p.stderr


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return {s["codec_type"]: s for s in json.loads(p.stdout)["streams"]}


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + f"{name}: {detail}")
    if not ok:
        fails.append(name)


# 0) synthetic source: moving test pattern + quiet 220 Hz "speech" (about -26 LUFS)
gate = "+".join(f"between(t,{s},{e})" for s, e in SPEECH)
src = OUT / "src.mp4"
run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", f"testsrc2=s=1080x1920:r={FPS}:d={DUR}",
     "-f", "lavfi", "-i", f"aevalsrc='0.05*sin(2*PI*220*t)*({gate})':s=48000:d={DUR}",
     "-shortest", "-threads", "2"] + r.encode_args("veryfast", 23) + [str(src)])

# a) silence detect -> plan -> remap words
step = r.silence_detect_cmd(str(src), noise_db=-40, min_gap=0.5)
sil = r.parse_silencedetect(run(step.argv), DUR)
check("silences found", len(sil) == 2, sil)
keep = r.plan_keep_segments(DUR, sil, words=WORDS, fps=FPS, pad=0.1)
tm = r.TimeMap(keep)
# two 1.5 s gaps, each shrunk by pad 0.1 on both sides -> 1.3 s cut each -> 7.4 s
check("keep plan", len(keep) == 3 and abs(tm.duration - 7.4) <= 1 / FPS, f"{keep} -> {tm.duration:.3f}s")
words = r.remap_words(WORDS, tm)
check("words kept + re-timed", len(words) == 3 and all(w["end"] <= tm.duration for w in words),
      [(w["word"], w["start"], w["end"]) for w in words])

# c) zoom markers live on the OUTPUT timeline (remap source markers first)
markers = r.remap_times([0.5, 4.0], tm)
wins = r.plan_zoom_windows(markers, tm.duration)
out = OUT / "trim_zoom.mp4"
run(r.trim_zoom_cmd(str(src), str(out), keep=keep, zoom_windows=wins, threads=2).argv)
st = probe(out)
vd, ad = float(st["video"]["duration"]), float(st["audio"]["duration"])
check("output size", (st["video"]["width"], st["video"]["height"]) == (1080, 1920), "1080x1920")
check("video length = plan", abs(vd - tm.duration) <= 1 / FPS + 1e-3, f"{vd:.3f} vs {tm.duration:.3f}")
check("audio length = video", abs(ad - vd) <= 0.03, f"audio {ad:.3f} / video {vd:.3f}")
for name, t in (("zoom_off", 0.1), ("zoom_up", wins[0][0] + 0.12), ("zoom_peak", wins[0][0] + 0.8)):
    run(["ffmpeg", "-hide_banner", "-y", "-ss", f"{t:.3f}", "-i", str(out), "-frames:v", "1",
         "-vf", "scale=270:-2", str(OUT / f"{name}.png")])

# b) loudnorm two-pass on the cut result, then re-measure
m = r.parse_loudnorm(run(r.loudnorm_measure_cmd(str(out)).argv))
check("pass 1 measured", m is not None, m and {k: m[k] for k in ("input_i", "input_tp")})
final = OUT / "final.mp4"
run(r.loudnorm_apply_cmd(str(out), str(final), m).argv)
m2 = r.parse_loudnorm(run(r.loudnorm_measure_cmd(str(final)).argv))
check("integrated -14 LUFS", m2 and abs(m2["input_i"] + 14) <= 1.0, m2 and m2["input_i"])
check("true peak <= -1 dBTP", m2 and m2["input_tp"] <= -0.7, m2 and m2["input_tp"])
check("video untouched by loudnorm", abs(float(probe(final)["video"]["duration"]) - vd) < 1e-3, "stream copy")

print("\nALL PASS" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
