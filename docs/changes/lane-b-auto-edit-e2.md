# Auto Edit E2 — motion + time effects (lane-b)

- `retention.motion_filter` (zoom stage, source time, before watermark/captions): punch, slow push, zoom-out, camera
  shake, flash (eq), whip (offset + horizontal blur on both sides of a cut seam). One scale + crop (+ blur/eq).
- `retention.warp_pieces/warp_graph` (cut stage, after captions are burned, so captions hold/stretch in sync):
  freeze frame (tpad clone + silence) and slow-mo (setpts + atempo); crossfade only across cuts.
- `edit_director`: RENDERED_EFFECTS = all motion + time effects (emoji = E3); motion_events / warps / time_extra /
  keep_of. Posted length (`rule_checks._duration`, editor output, Review `output_seconds`) includes freeze/slow-mo.
- Editor: each plan item has an effect picker; timeline cache `pieces` maps preview ↔ source time with warps.
- Verified on staging (lane-b-e1 clip 2d79eef6): cut 14–15 s + 8 items, one per effect; worker log "motion from the
  plan: flash, push, shake, whip, zoom_out" + "39.9 s -> 40.7 s + time effects (freeze, slowmo)", preview 40.7 s.
  Frames at each effect's peak: watermark + captions sharp and in place (whip, flash, shake), nothing off-canvas.
  Unit: tests/test_motion.py (8). UI: editor.spec "Auto edit E2 effects".
