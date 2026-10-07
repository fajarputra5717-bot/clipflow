# 2e3d583 (lane-b) P4 task 5: Effects + Audio tabs — QA 2026-10-07

Live on lane-c-a clip 884938b3 (cuts + zoom already set), staging 2e3d583: progress bar on (#FFD60A), compression on,
an extra pause cut 20.0–20.7 s (real pause, next word at 21.56 s) through cuts + audio.silence_ranges.
- lane-c-b PUT …/editor/progress and …/audio on A's clip → 404 both.
- Worker: "Progress bar: 5 segment(s)", "Cuts: 5 segments, 33.0 s -> 30.8 s + light compression", then loudnorm last
  (worker.py:5549→5551, 6018→6021).
- Final 1080x1920, 30.763 s, -14.1 LUFS / -1.1 dBTP measured (ebur128).
- 3 frames (1 / 18.5 / 30 s, frames/lane-b-2e3d583-effects.jpg): bar fill grows continuously across the pause seam (~60 %
  at 18.5 s, ~97 % at 30 s); watermark, captions and karaoke unchanged; zoom still applied.
- Playwright on staging a5c3da5 (includes 2e3d583): 181 passed, 0 failed, 7 skipped (lane-b suite + qa-multiuser).
  An earlier run showed 33 failures because staging was rebuilt mid-run (2e3d583 → a5c3da5, frontend bind mount). Invalid.
Bugs:
1. Low: normalize_audio stores silence_ranges unchecked against the clip: [[-1,2]] and [[0,9999]] return 200 and are stored
   ([[5,3]] is dropped). They're only bookkeeping for undoing Remove silences (the real cuts go through the validated cuts
   route), so there's no render effect. Clamp them like cuts.
Merge: OK.
