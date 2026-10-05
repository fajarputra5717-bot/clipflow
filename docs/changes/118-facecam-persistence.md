# 118 · Facecam = a persistent, steady box in a corner/edge; game faces no longer get a panel (Lane C: junk panel on fresh GTA imports) · worker.py

**Found by Lane C.** Two of three fresh GTA RP imports (fbda481f, 7e84933b) got the camera panel with a junk
crop: in-game character faces were detected. 7e84933b: both clips "found" a face mid-frame → majority → panel;
fbda481f: a 1-of-2 tie whose hit sat at the right edge with 3 detections → passed 101's tie test.

**Measured** (16 sampled frames per clip): real facecams (4 jobs) are present at the same place and size in
75–100 % of frames (spread ≤ 0.011); every false positive was in 6 % (1 frame of 16).

**Now.**
- `_detect_face_raw()` records which sampled frame each detection came from and returns `persistence` = share
  of sampled frames with a face within 4 % of the frame of the median position at a similar size (±35 %).
- `facecam_like()` = corner/edge region AND ≥ 3 hits AND spread ≤ 0.03 AND persistence ≥ 0.5.
- Job decision (`decide_face_layout`): only facecam-like hits count; panel if they're at least half the clips
  (so a real facecam with one missed clip keeps the panel), else full-frame. Log lists every hit with region,
  hits, persistence, spread and verdict.
- Per clip with layout auto: a detection that isn't facecam-like is dropped ("no panel", logged). A left/right
  hint still trusts the detection.

**Verified:** dry run + backfill of all 19 multi-clip jobs: only fbda481f and 7e84933b changed (panel → full);
the Fandra facecam jobs stay panel (cam in 88–100 % of frames); re-rendered finals cfb5104c (fbda481f) and
a63edbbb (7e84933b) are full-frame (`face_crop.panel=false`, frames checked), Fandra preview 8c7795ef keeps the panel.
