# 101 · Facecam tie rule: corner/edge region + persistence, reason logged (pre-P1 #3, QA Medium) · worker.py

**Before (095).** A 1-of-2 tie got the camera panel only if ≥ 2 hits agreed in position, which a single hit
never can: a facecam stream whose other clip missed the face went full-frame for both (QA 981a001 #1).

**Now.** In a tie, `decide_face_layout()` uses the camera panel if a hit is `facecam_like()`: centre in a
corner (outer third both ways) or the bottom band (y ≥ 75 %) **and** persistent (≥ 3 detections, spread
≤ 0.03); otherwise full-frame. The fallback box is the median of the facecam-like hits. The log names the
reason per hit: `tie: face at (0.29, 0.89) corner/edge, 17 hits, spread 0.002 → facecam`.
`_detect_face_raw()` now returns `spread` (largest median absolute deviation of the top detections' centre,
as a fraction of the frame), `hits`, `frame_w/h`.

**Why persistence too.** Measured on this box: the 4 facecam jobs → 15–37 hits, spread ≤ 0.012, centre
y 0.84–0.90. Every lone tie hit → 1–2 hits; two of them sit in a corner (GTA RP, (0.30, 0.17) and
(0.32, 0.16)), so position alone would have given a no-cam video a junk panel again.

**Verified:** re-backfill of 13 jobs: decisions unchanged (facecam majorities → panel, lone GTA / mid-frame
hits → full, each with its reason); simulated QA case (Fandra-style cam hit + one miss) → panel.
