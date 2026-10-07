# P4 task 4 — Zoom punch-ins: timeline markers, rendered via retention.py (lane B)

- `edit_spec.zoom = {on, intensity 0–100, markers: [source s]}` (`normalize_zoom`: sorted, ≥ 0.05 s apart, inside the
  clip, ≤ 40; intensity → peak 1.0–1.30, 50 = 1.15 = the retention engine's default). `PUT …/editor/zoom`
  (owner-scoped, 400/404/409, marks an existing final outdated).
- Render: zoom is part of `render_vertical()`'s graph right after the layout and BEFORE the watermark and the
  captions (agreed render order), so text never zooms: `render_steps.zoom_stage()` (one hook inside
  render_vertical) appends `retention.zoom_filter(plan_zoom_windows(markers))` (smoothstep 1.0 → peak → 1.0, per-frame
  scale + fixed crop, overlapping punch-ins merge into one hold). The clip comes from a ONE-SHOT context set by
  `render_steps.begin_render()` (one hook before render_vertical in preview and final), consumed by the next
  zoom_stage, so other render_vertical callers (clean plate) never zoom. Times = clip-relative source seconds
  (render_vertical input-seeks to the clip start) = the editor's basis; cuts happen after.
- Editor timeline: "◆ Zoom" mode (key Z): click the timeline/a word to add a punch-in, click a ◆ to remove it;
  "+ Zoom at playhead"; marker lane above the waveform with the planned zoom window shaded; debounced save;
  Render preview flushes it. The Effects tab (intensity, on/off) is task 5.
- Tests: `tests/test_zoom.py` (6), 2 UI specs × 2 viewports.
