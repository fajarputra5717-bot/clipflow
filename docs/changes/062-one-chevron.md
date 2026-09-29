# 062 — One disclosure affordance: rotating chevron + aria-expanded (TASKS-UI-QA T5)
Date: 2026-09-29 · Commit: see `git log --grep "UI-QA T5"` · Files: frontend/html/index.html · UI v2.1106

## What changed
- The Settings disclosures (Advanced, Watermark, and the AI/FACE/… groups rendered by `loadSettings`) used a `＋/−`
  glyph swap. They now use the shared `.chev`: a 16 px down chevron, `--muted`, that rotates 180° over 200 ms
  (`var(--ease)`). Every `<summary>` in the app now uses it: Import Options, edit-drawer Description/Thumbnail/
  Watermark, Version history, and the Settings rows.
- One rule for every row: the whole `<summary>` is the hit target, `min-height:44px`, and the chevron sits on the
  trailing edge (`summary > .chev{margin-left:auto}`). Per-component heights (42/44/padding) were removed.
- `aria-expanded` is on every `<summary>` in the markup/templates (edit-drawer ones reflect `editMoreOpen`). The
  existing capture `toggle` listener on `document` keeps it in sync for any `<details>`.
- Sidebar hide/show keeps its distinct panel icon (a different action), resized 18→16 px with the stroke matched to
  the chevron's 1.8 px. Same `--muted` colour. It already had `aria-expanded`.

## Why
ui-audit.md §1: three affordances (`＋/−` swap, chevron, a default `▸` on the leading edge), no animation on Settings,
and no `aria-expanded` on native disclosures.

## Decisions & trade-offs
- `aria-expanded` on a native `<summary>` is redundant for Chromium's a11y tree, but the task asks for it
  explicitly and it makes the state queryable by tests. It is kept in sync by one listener, not per element.
- The Settings `<details>` lost their 9 px vertical padding (the 44 px row replaces it). The open state keeps 9 px at the bottom.

## Gotchas for future changes
- New disclosure → `<summary aria-expanded="false">…<span class="chev" aria-hidden="true"></span></summary>`. The
  shared rules handle size, position and rotation. Don't add a new glyph or a `::after` marker.

## Verification (headless Chromium, :8081, /api mocked so settings groups and a candidate drawer render)
All 15 summaries: chevron 16×16, `rgb(110,110,115)`, `transition: transform 0.2s`, trailing offset 0, row 44 px.
Clicking 4 px from the left edge toggles open, `aria-expanded` true, rotate 180. Clicking again → false, 0. Sidebar
icon 16×16, stroke 2.7 (=1.8 px), same colour. No page errors. Not checked: Safari/Firefox, a real screen reader.
