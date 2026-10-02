# P0 gate checklist (draft, QA's working list; the verdict goes in gate-P0.md when Lane A reports P0 complete)

Source: docs/roadmap.md P0 row (incl. 11e69a9 additions) + owner's fold-ins of QA lows (2026-10-02).
P0 gate runs WITHOUT Playwright. Any open High = BLOCKED.

## Fresh-import e2e (sequential, idle queue)
- [ ] ime-roleplay job: first preview + final → karaoke frames, layout, watermark (campaign asset, ≥ 16 %), −14 LUFS / TP ≤ −1 dBTP, hashtags exact order at caption end, title rules
- [ ] fandra-octo job: same checks

## Roadmap P0 items
- [ ] Loudness on Submagic "use as final" path (apply_watermark_overlay)
- [ ] Loudnorm failure → final kept + UI warning (not a failed render)
- [ ] Loudnorm disk reserve ≈ 2× file size
- [ ] Previews: single-pass loudness
- [ ] Unresolvable campaign watermark → failing chip + log, no silent fallback to the active watermark
- [ ] Hashtags at the END, exact order; rules files say "order", not "prefix"/"first in the caption"
- [ ] Minimum analysis window 10 min (settings PUT rejects less)
- [ ] Watermark height min 16 % in Settings (no silent clamp)
- [ ] `WHISPER_LANGUAGE` labelled "Fallback language"
- [ ] Version badge bumped (incl. for 090)
- [ ] Per-job layout; full-frame caption height (captions clear of in-game HUD when panel=false)
- [ ] Island-style capsules for row progress: Import job cards (index.html:1650), Publish queue rows (:1712); no separate bar design remains

## 090 lows folded into P0 (owner 2026-10-02)
- [ ] Failed /api/activity poll: keeps last known tasks, retries with backoff, logs to console (not swallowed)
- [ ] Activity job filter is an ALLOWLIST of running states (a new status never shows as running)
- [ ] Submagic shows an indeterminate island state ("Submagic · processing"), no fake 50 %

## Carry-over (not P0 scope; listed so the gate states them)
- lane-b df5445a #1 (Medium): IME advice "not eligible" after Oct 28; blocks P2/P3, not P0
