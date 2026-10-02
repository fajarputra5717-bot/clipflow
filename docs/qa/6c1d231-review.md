# QA review · 6c1d231 · 091 loudness on previews + Submagic finals, never fatal (render_warnings chip), 2× disk reserve (P0)

Reviewer: Lane C · 2026-10-02 · deployed worker confirmed; fresh-import job 127cb629 (GTA RP source, layout auto)

Code checked: `render_warnings` via `ensure_schema` (JSONB) and returned by `get_job` (`c.*`) · `set_render_warning()`
SQL handles NULL/add/replace/clear (empty → NULL) · `normalize_loudness()` catches everything except
`JobCancelled`, keeps the un-normalised file and sets the "loudness" chip; success clears it · disk guard
`need_mb = 2 × file + 1` · previews: same two-pass chain at 96k, no ebur128 re-measure · Submagic apply path
now calls it with the clip duration · chip uses `--badge-warn-*` (defined in both theme blocks) and
`role="status"`, not a progress UI (island rule OK).

## Re-check (fresh import → first preview → final)
| candidate | panel | preview I / TP | final I / LRA / TP | verdict |
|---|---|---|---|---|
| 9c4473e1 | **true** (false positive) | −14.3 / −0.9 dBTP | **−14.2 / 10.0 / −1.2** | loudness PASS, layout FAIL |
| abea5490 | false | −15.9 / **−0.1 dBTP** | **−15.8 / 11.4 / −1.2** | loudness off target |
Karaoke sweeps in abea5490's final (`frames/recheck-091/final-abea5490-captions.jpg`). No render warnings set.

## Findings (most severe first)
1. **Medium · a final can miss the target by ~2 LU silently.** abea5490 (input −30.1 LUFS / −7.5 dBTP, peaky game
   audio) ends at −15.8 LUFS: +16 dB of gain would break the −1 dBTP ceiling, so `loudnorm linear=true` can't
   apply it linearly and the limiter eats the rest. The ebur128 re-measure (`after`) is logged, but nothing
   compares it with the target: no chip, no corrective pass. Suggest: if |I − (−14)| > 1 LU, run a second
   pass on the result (or a dynamic-mode pass), and set a "loudness off target" chip if it's still off.
2. **Medium · junk bottom panel is back through a face false positive** (087 #1 materialised). Same no-facecam
   source, layout auto: 9c4473e1's detector found a "face" (game character) → `panel=true` → the bottom 30 % is
   a crop of the source's chat overlay ("00:46 … belum") in preview AND final
   (`frames/recheck-091/preview-9c4473e1.jpg`, `final-9c4473e1-50.jpg`). The roadmap's P0 "per-job layout" item
   should cover it; QA will re-check it on the P0 gate.
3. **Low · preview true peak −0.1 dBTP** (abea5490). Previews skip the re-measure and are encoded at 96k, where
   AAC overshoot eats the 0.5 dB headroom. Not published, but a preview near 0 dBTP can clip on playback.
4. **Info · roadmap said "single-pass on previews"**; 091 deliberately uses the same two-pass chain (documented:
   single-pass measured −15.5 / −0.8). Fine with QA.
5. **Process · Lane A recreated backend + worker at 14:47:50 while QA's final render (abea5490) was running.** The
   render completed, but its worker log was lost. Please announce restarts or check `/api/activity` first.

## Not verified
- Submagic "use as final" loudness (the export is billable; never auto-triggered). Code-read only.
- Failure path → chip (would need a forced ffmpeg failure; code-read only).
- Disk-reserve refusal with a nearly full disk.
