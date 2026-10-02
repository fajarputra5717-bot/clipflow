# QA review · 1dfb5ad · 101 facecam tie rule: corner/edge + persistent detection → panel (closes gate-P0 #3)

Reviewer: Lane C · 2026-10-02

Tie → `panel` if a hit is `facecam_like()`: centre in a corner (outer thirds) or the bottom band (y ≥ 0.75),
≥ 3 detections, spread ≤ 0.03 (calibrated on this box: real cams 15–37 hits, spread ≤ 0.012, cy 0.84–0.90; lone
in-video hits 1–2, mid-frame/top). Reason logged per hit. Majority rules unchanged.

## Findings
0. **Medium (regression) · a static HUD element passes as a facecam: the junk panel is back on ALL clips of a
   no-cam source.** Fresh GTA RP job fbda481f (IME's source, layout auto): 1/2 clips "detected" a face at
   (0.94, 0.67), 3 hits, spread 0.002 → `facecam_like` → job `panel` → BOTH finals have a zoomed bottom panel
   (character shoulder / asphalt), `frames/recheck-100-101/final-*.jpg`. The hit is the game's right-edge HUD list:
   static, so "persistent" is exactly what a HUD is. Before 101 (095's position-agreement rule) this source went
   full-frame. Deterministic on this source; workaround: import with "No facecam". Suggest: require the hit to look
   like a face over time (spread of size too, or hits ≥ 10 like the calibrated real cams 15–37), or require the
   detector score, not just position stability; and keep a `full` decision when only 1 clip of 2 detects anything
   in the outer 10 % edge band.
1. **Low · centred top or mid-side cams fall back to full-frame on a tie** (e.g. a cam at top-centre: not a
   corner, not the bottom band). Rare on this box's sources; the log line names the reason, so it's diagnosable.
2. Info · thresholds are calibrated on 4 facecam jobs; revisit when new streamers are added.

## Re-check: FAIL (see #0)
Log: "Face layout for the job: panel (1/2 clips detected a face; tie: face at (0.94, 0.67) corner/edge, 3 hits,
spread 0.002 → facecam)".
