# QA review · 8e51f32 · 116 keyword colour defaults to one that contrasts with the style highlight (closes gate-P1 #5)

Reviewer: Lane C · 2026-10-03 · deployed worker confirmed

`shared/edit_spec.contrasting_keyword_color()` = first of the palette (#FFD60A, #30D158, #FF453A, #64D2FF, #BF5AF2,
same order as the UI's `KW_COLORS`) at RGB distance ≥ 120 from the style highlight; `make_ass` uses it when no colour
is saved; the UI mirrors it (`kwAutoColor`, Math.hypot ≥ 120) and no longer saves the auto colour on Apply, so an
explicit choice still wins.

## Re-check: FIXED (fresh import)
QA job af701859 (GTA source, layout "No facecam", default outline + karaoke, AI keywords [kekuatan, sihir, molotofan,
fix], no colour saved): at 2.2 s the karaoke sweep word "INI" is yellow and the keywords "KEKUATAN SIHIR" are
**green**, in the first preview and the final (`frames/recheck-116/`). Layout "No facecam" → clean full-frame (the
gate-P1 #1 workaround works on this source).

## Findings
1. **Low · a final can still ship above −1 dBTP (with the chip).** Same final: pass 1 −14.2 LUFS / +0.1 dBTP →
   corrective pass (headroom 1.9 dB) → −14.4 / **−0.6 dBTP**, 2 samples; chip "Loudness still off after a corrective
   pass" set as designed (100). The limiter at −2.9 dBFS still comes out 2.3 dB hotter after AAC on this transient: a
   true-peak limiter on the encoded output (or a lower ceiling + oversampled limiter) would make the second pass
   reliable. Not silent, so Low.
