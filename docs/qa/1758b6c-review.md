# 1758b6c (lane-b) zoom context bound to the render's output path (fixes QA 8cf6088 Low) — QA 2026-10-07

Code: begin_render(candidate, duration, output_path), and zoom_stage applies only when render_vertical's output_path equals the
announced one, then always clears. Both call sites pass the same path to begin_render and render_vertical (preview_path in
create_preview, output_path in the final). A stale context can't reach render_clean_plate (different path) or a caller
without a path. Fixed.
Live (staging = 1758b6c): lane-c-a clip 884938b3 preview re-render → "Zoom: 2 punch-in(s), peak 1.30". The zoom still applies.
Not verified: tests/test_zoom.py (Lane B: 135 OK; no pytest on the host).
Merge: OK.
