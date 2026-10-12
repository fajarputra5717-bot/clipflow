# Auto Edit — edit director + style packs (lane-b)

Goal: one click gives a clip a restrained, reviewable edit (motion, overlays, SFX, look). The AI only *proposes*;
every item is a toggleable marker the user can turn off. Built in parts on lane-b, staging only, one commit
each, Lane C reviews each part before the next.

## Data
`edit_spec.director = {version, generated_at, pack, items: [{id, t, effect, params, reason, on, source}]}`
- `t` = clip-source seconds (like zoom markers), re-timed through cuts with `retention.TimeMap` at render.
- `source` ∈ `transcript | audio | cut | vision`, `reason` = one short line shown on hover.
- Normalised in `shared/edit_spec.py` (`normalize_director`); unknown effects are kept but not rendered
  (so a plan made by a newer build degrades safely).
- Render order stays: cuts → zoom/motion → hook card + captions (ASS) → overlays/emoji → watermark → look
  → SFX mix → loudnorm (always last).

## E1 · Edit plan (this part)
- `shared/edit_director.py` (pure, unit-tested):
  - `moments_prompt()` + `parse_moments()`: utility AI labels hook / punchline / shock / laugh moments with
    timestamps from the clip's timed words (router task `edit_moments`, `TEXT_UTILITY_PROVIDER`).
  - `loudness_peaks(peaks, rate)`: local maxima in the timeline waveform (already cached per preview).
  - `cut_points(cuts)`: seams the user made (candidates for transitions in E2).
  - optional vision: 4–6 frames (320 px JPEG) from the preview to the utility model → reaction peaks.
    Router gets an optional `images=` argument (Gemini parts / Claude image blocks); off with setting
    `EDIT_DIRECTOR_VISION=false`; any vision error = plan without vision (logged), never a failure.
  - `plan()`: merge signals → items, then **restraint** (deterministic): ≥ 3 s between effects, nothing inside
    the hook title card window, nothing inside removed ranges, ≤ 1 effect per signal cluster; overlay items
    (E3) carry a position that avoids the caption band and the watermark rect.
- API: `POST …/editor/plan` (generate / regenerate, synchronous, utility model, 1 attempt per provider),
  `PUT …/editor/plan` (toggle items). Owner-scoped like the other editor routes.
- UI: Effects tab "Auto edit" group (Generate / Regenerate plan, count, list with switches); timeline lane
  with one marker per item (colour per effect), click = toggle.
- Rendering in E1: only `punch` (maps onto the existing zoom stage). Other effects show as "arrives in E2/E3/E4".

## E2 · Motion
Zoom variants (punch, slow push, zoom-out), camera shake, flash, freeze frame, speed ramp / slow-mo, whip at
cuts. Builders in `shared/retention.py` (pure argv/filter strings + tests); speed changes and freezes re-time
words/captions through a `TimeMap` built from the same segments.

## E3 · Overlays + SFX
- Emoji pop-ups as PNG overlays (libass can't draw colour emoji). Set: **Twemoji** graphics, CC-BY 4.0
  (not CC0): attribution in `assets/LICENSES.md` + docs. Positions avoid captions + watermark.
- SFX (whoosh, boom, bass hit, ding, laugh, record scratch): **CC0 sources only**, each file listed in
  `assets/sfx/LICENSES.md` (source URL, author, licence). Mixed under speech with sidechain ducking; loudnorm
  stays the last audio step.

## E4 · Look
Colour presets via ffmpeg `eq`/`curves` (or a bundled .cube LUT): Vivid Gaming, Warm, Moody; vignette; light
grain. Applied after overlays, before encode; previews and finals identical.

## E5 · Style packs
Gaming Hype, Funny/Meme, Drama/Tension, Podcast Clean = **definition pending from the owner** (the brief was
cut off). Assumed shape: a pack = director weights (which moments → which effects, density) + look preset +
SFX set + caption preset; picking a pack regenerates the plan.

## Open questions
1. E5 pack definitions (see above).
2. Vision default: on (4 frames, utility model) or off until we see the cost?
