# P4 task 3 — Cuts: words/pauses, silence suggestions, trim handles, output readout (lane B)

**Model.** `edit_spec.cuts = {trim: [a, b] | null, removed: [[s, e], …]}` in clip-relative SOURCE seconds
(`shared/edit_spec.normalize_cuts`: sorted, merged, clamped to the trim window, ms precision, ≥ 1 s kept,
≤ 400 ranges; whole-clip trim and nothing removed = key removed). Saved by
`PUT /api/jobs/{jid}/candidates/{cid}/editor/cuts` (owner-scoped, 400/404/409, marks an existing final
outdated, 114); `GET …/editor` returns `cuts` + `output_seconds`.

**Render.** After `render_vertical` (captions, karaoke and the hook card already burned at source times),
`render_steps.apply_cuts()` cuts the rendered file with `retention.silence_trim_graph` (keep segments
from `cut_plan()`, frame-snapped to the file's probed fps, 40 ms equal-power audio crossfade per seam) via
the worker's `run_command` (cancel + watchdog timeout). Karaoke survives by construction: the burned
captions are cut together with the video, nothing is re-timed by hand. Loudnorm still runs last. The hook
card is shifted to start at the first kept moment and to fill its 2/2.5/3 s of the OUTPUT
(`card_window`). Preview and final share the code (two one-line hooks, `# lane-b hook`).

**Timeline (v2).** Built from the SOURCE clip window (not the cut preview), so cut words stay visible
and restorable; the cache also stores the `keep` segments the preview was rendered with. The editor maps
video time ↔ source time through that `keep` (playhead, click-to-seek). v1 caches are ignored.

**UI.** Timeline header: Seek / ✂ Cut mode (key C), "Cut N pauses ≥ 0.6 s" (suggestions = word gaps, each
cut with 0.12 s of the pause kept on both sides), Restore all, "Output N s" readout (also in the footer
state). Cut mode: click a word or pause chip to cut (struck through, red hatched band on the waveform),
click again to restore. Orange trim handles at both ends: drag (pointer/touch) or arrow keys (Shift = 1 s),
outside shaded. Debounced save (600 ms); Render preview flushes pending saves first.

**Verified** — see the update section below.

## Verified on staging (2026-10-06)

Clip 65dbd109 (35.0 s, 69 words): cuts = trim 1.0–30.0 s + two adjacent words (merged to 5.93–6.30) + one
suggested pause (1.58–2.66, padded). Editor readout 27.56 s → cut preview AND final 27.55 s video /
27.56 s audio (frame-snapped keep [[1.0,1.583],[2.667,5.933],[6.3,30.0]]); final −14.2 LUFS (loudnorm still
last); hook card shifted to start at the trim (0.0 s of the output). Karaoke frame check (uncut preview at
source t vs cut preview at mapped t, first word after each cut): identical caption state, same highlighted
syllables ("…GAK MUN|GKIN DAMAS", "S|UMPAH"); SSIM 0.99 on the first pair, the second is dominated by the
flickering game HUD inside the caption band (its ±0.4 s control is just as low) so it was judged visually.
Live UI (1280): 14 struck words + 2 struck pauses from the saved spec, trim handles at 1.0/30.0, "Output 27.6 s",
click word 12 (source 6.30 s) → video 3.85 s = mapped output time, chip highlighted, no errors.
Tests: `tests/test_cuts.py` (9), 4 cut UI specs × 2 viewports; UI suite on staging 88 passed; unit OK.
Also: STAGING strip offsets the sticky toolbar (22 px) on staging only.

## Fix 2026-10-07 — cut words no longer stay on screen (QA 3597000 / 8f361a3, HIGH)

Burning at source times and then cutting kept a caption LINE's full text when the line spanned a cut
("FINALITY GAS AJA" / "GOALIN AJA AMAN" after cutting "gas aja goalin"). Now `render_steps.burn_segments()`
(one `# lane-b hook` before make_ass() in preview AND final) removes cut and outside-trim words from the caption
segments that get burned (a word is cut when > 50 % of it is removed), rebuilds each line's text from its kept
words and drops empty lines. Kept words keep source timings and are mapped to output time by the cut pass
(time-remap with the video), so karaoke stays intact. The editor timeline still gets the full word list.
Verified on staging (clip 65dbd109, 3 mid-line cuts: "yang", the 2nd "gak", "5"): burned preview AND final ASS read
"ITU MX", "GAK ADA INI MUNGKIN DAMAS", "KEPALAH PAS COIN TOH"; frames 0.15 s before/after each cut (preview) and
after each cut (final) show the lines without the cut words and the karaoke highlight advancing across the cut
("GAK ADA I|NI…" → "…MUNG|KIN"); final 33.79 s = 35 − cuts. `subtitle_segments` (stored) = what was burned, still in
SOURCE time (QA Low #2, documented here). Tests: 3 new in tests/test_cuts.py; unit 112 OK.
