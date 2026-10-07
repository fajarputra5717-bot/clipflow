# 160 · Fix: "Get another hook" no longer carries the old clip's cuts / keywords / zoom markers to the new moment · main.py

- **Bug (Lane B report, 2026-10-07):** `new_hook` moves start/end but kept `clip_candidates.edit_spec`, whose
  time-based keys are in the OLD clip's time: cut 10–15 s, Get another hook → the new preview had 10–15 s removed
  (same for zoom markers, keyword words, silence ranges).
- **Fix:** the same UPDATE strips `cuts`, `keywords`, `zoom.markers`, `audio.silence_ranges` and `hook_title.text`
  (the card text belonged to the old moment); style choices stay (caption preset/position, keyword colour, zoom
  and audio on/off + intensity, hook card on/duration). Empty spec → NULL.
- Also: `payouts.describe()` says just "Payout not set yet" (no parser note).

**Verified:** the expression on a sample spec (SELECT, no write) keeps `{zoom:{on}, audio:{trim}, caption,
hook_title:{on,duration}, keyword_color}`; NULL / cuts-only → NULL; backend deployed healthy.
