# Auto Edit E4 — look (lane-b)

- `edit_spec.look = {preset: none|vivid_gaming|warm|moody, vignette, grain}` (`normalize_look`), `PUT …/editor/look`,
  Effects tab "Look" group (preset chips, Vignette + Light grain switches). Packs (E5) will preset it.
- `retention.look_filter`: ffmpeg eq/colorbalance (no LUT files to license); vignette `vignette=angle=PI/5`, grain
  `noise=alls=6:allf=t`. Warm shifts mids/highlights only (shadows untouched, blacks stay black).
- Zoom stage order: motion → look → emoji → (watermark, captions). The look grades the FOOTAGE only: emoji, caption
  colours and the watermark stay exact. Previews and finals use the same stage.
- Verified on staging (lane-b-e1 clip 0782e50b, Moody + vignette + grain + 😱): log "Look: moody + vignette + grain";
  preview and 1080x1920 final frames: footage graded with vignette, emoji full colour, captions yellow/green, watermark
  white. Final -14.3 LUFS / -5.3 dBTP. Unit: test_overlays_sfx Look (2). UI: editor.spec "E4 look".
- Also in this round: plan params validated (5d8cdde, QA b85de37 Low): unknown sfx/emoji/param or out-of-range → 400.

## QA 7b9854f Lows
- Render cost: `colorbalance` works in RGB (two colour-space conversions per frame). Looks are now YUV-only (`eq` +
  `lutyuv` chroma shifts). Timing on 20 s of preview footage, 2 CPUs (staging worker limit), x264 veryfast: no look 2.3 s;
  vivid 8.3 → 3.7 s, warm 7.1 → 2.6 s, moody 7.0 → 2.5 s; vignette + grain together 4.0 s. Finals (1080x1920) scale
  the same way: expect roughly +10–60 % of the encode time for a look, most with Vivid Gaming (unsharp) and grain.
- Warm was barely visible: now a clear amber chroma shift (u −5, v +6) with saturation 1.12; blacks stay near black.
