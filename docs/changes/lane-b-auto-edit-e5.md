# Auto Edit E5 — style packs (lane-b)

- `shared/style_packs.py` = the owner's four packs (2026-10-12): caption preset + keyword colour, moment → effect +
  sound mapping (cycled per kind), density, look, progress bar, Loud & punchy, zoom intensity. Campaign defaults: IME +
  Fandra → Gaming Hype, everything else (and none) → Podcast Clean. `resolve(spec, campaign)` = the clip's own
  `edit_spec.pack` or the campaign default ("from campaign" tag).
- `edit_director.plan(mapping=, min_gap=)`: kinds the pack doesn't list are skipped. `POST …/editor/plan` always
  uses the clip's pack. `POST …/editor/pack {pack}` writes pack, caption, keyword_color, look, progress, audio.loud,
  zoom intensity, then regenerates the plan (no preview transcript yet → settings applied + `pack_note`).
- Editor: Effects tab "Style pack" chips (two-tap apply; the editor reloads and stays on Effects).
- Funny / Meme uses ding for laughs until a CC0 laugh recording exists. "Fails" = shock moments (slow-mo).
- Verified on staging (lane-b-e1 clip 0782e50b, no campaign → Podcast Clean by default): apply Gaming Hype → hormozi/
  bounce captions, keywords #30D158, vivid_gaming, progress on, loud on, zoom 60, plan of 3 punches (bass_hit/boom)
  ≥ 3 s apart and clear of the 2 manual zoom markers. Preview log: 5 punch-ins (3 from the plan), Look vivid_gaming,
  SFX 3 mixed, Loud & punchy, -14.2 LUFS / -4.7 dBTP. Frame at a punch: progress bar, Hormozi caption, watermark ok.
  Unit: tests/test_style_packs.py (4). UI: editor.spec "E5 style pack".

## QA 8fdbdc1 Lows
- Peak guard keeps a 0.1 dB margin (`PEAK_GUARD_MARGIN`): an encoded file above -1.1 dBTP is re-limited. Throwaway
  container, a clip that landed at exactly -1.0: "peak guard 1: -1.0 → -14.5 LUFS / -1.4 dBTP".
- The pack's second tap now says what it replaces: "Tap again: replaces captions, look, sounds, plan".
