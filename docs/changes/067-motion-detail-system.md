# 067 — Motion & detail system (HIG UX pass)
Date: 2026-09-29 · Commit: see `git log --grep "067"` · Files: frontend/html/index.html, CLAUDE.md · UI v2.1107

## What changed
- **Tokens** in `:root` (dark overrides where the value differs):
  - curves `--ease-out` cubic-bezier(.32,.72,0,1) (the old `--ease` now aliases it), `--ease-spring`
    (.34,1.4,.64,1, a gentle overshoot) and `--ease-in-out`
  - durations `--dur-1..4` = 120/200/320/450 ms
  - `--press` .97, `--sp-h/1..5` (4/8/16/24/32/40 px), `--hit` 44 px
  - `--font-text` / `--font-display` (-apple-system first)
  - `--ring` focus halo, `--hairline`, and materials `--material-thin|--material|--material-thick` + `--material-blur`
- **Normalised:** all 70 `transition` declarations moved to the 4-step duration scale (they had 14 distinct values).
  9 one-shot entrance animations were mapped the same way; loops are unchanged. Every `:active` press is
  `scale(var(--press))` (was .9–.985 in 14 places). Hover no longer lifts (`translateY(-1px)` removed); it changes
  colour and shadow only. Every `backdrop-filter` uses `--material-blur`.
- **Detail:** the sidebar is a material surface (translucent + blur, hairline edge). Labels are sentence case (the
  uppercase `.rail-title` is gone, "BETA" → "Beta"). Container, panel, field, status-box and sidebar spacing are on
  the 8pt grid. Buttons have `min-height: var(--hit)`. Icon buttons are 44×44. The version chip and the rename
  pencil keep their visual size with a 44 px invisible hit area (`::after`). The focus ring (outline + `--ring`)
  now also covers `role=tab` and the file-upload label. Headings use the display stack.
- **Reduced motion:** the existing global CSS rule still covers all CSS. New `motionMs(ms)` collapses JS waits that
  exist only for an animation (list/detail switch, tab switch, status fade) to 0.

## Decisions & trade-offs
- The caption-preview keyframes (`cpw-*`) and their curve keep their old values: they mirror the ASS timing burned
  into the video, so the preview must not follow UI motion tokens.
- 44 px applies to all buttons, even on desktop (iOS sizing). Tiny chips extend their hit area instead of growing.
- The tabs pill (37 px) is left alone because 072 removes it. The watermark buttons (21 px) are rebuilt in 071.

## Verification (headless Chromium, :8081, /api mocked; light/dark × 1280/800/390)
0 console or page errors. Every visible control hit-tests to itself (elementFromPoint). Under `reducedMotion:reduce`,
0 running animations after load, theme toggle, tab switch, opening Options and pressing Analyze
(`document.getAnimations()`).
