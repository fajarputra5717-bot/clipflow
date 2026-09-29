# 013 — Display caption fonts (R-19)
Date: 2026-09-29 · Commit: see `git log --grep R-19` · Files: shared/fonts.py, worker.py, main.py, index.html, docker-compose.yml, frontend/conf.d/default.conf

## What changed
- `shared/fonts.py`: `CAPTION_FONTS`, the one list backend + worker agree on (6 system fonts + 11 display fonts from
  064's `worker/fonts/`). Names carry the weight: Montserrat Black/ExtraBold/Bold, Inter Black/Bold, Oswald Bold,
  Poppins ExtraBold/Bold, Anton, Bebas Neue, Archivo Black.
- `make_ass()`: font resolved through the catalog (`resolve_caption_font`), and the Style line's Bold comes from
  `caption_font_bold()`: **0 for every display font** (weight via the family/full name, no libass faux bold); system
  fonts keep the preset's Bold exactly as before.
- Backend `normalize_subtitle_style()`: font validated against the catalog; an unknown name falls back to the default
  **with a log line** (REBUILD: a silent normalizer fallback once dropped the chosen font).
- Captions drop emoji (`strip_emoji()` inside make_ass's `esc()`): libass renders them as tofu/outline/blank (065).
- Edit panel: 17 fonts, each `<option>` styled in its own face; the live preview uses the real files (`@font-face`
  "CF …") and the font's own weight. nginx serves `worker/fonts` read-only at `/fonts/` (compose mount outside the
  html root + `location /fonts/`). Badge v2.1107.

## Why
R-19 (rebuild of TASKS-3 T1), following the libass spike's recommendations (065): weight via name, Bold=0, strip
emoji, reset per-word base values before `\t`.

## Decisions & trade-offs
- Per-word `\t`: today every chunk/word is its own Dialogue event and each entrance tag sets its own base values
  first, so the carry-over gotcha can't occur (verified in the generated ASS). Left a comment on
  `ANIMATION_ENTRANCE_TAGS` instead of adding unused reset code.
- Fonts served from the worker's directory, not copied into frontend/html (one copy, 2.5 MB).
- "Liberation Sans"/"Noto Sans"/"DejaVu Sans" still render bold (preset Bold=-1), unchanged from the baseline.

## Gotchas for future changes
- `fc-match "Montserrat Black"` falls back to Noto; that's expected. fc-match matches families, libass also matches
  full names. Verify fonts with ffmpeg `-v verbose` `fontselect:` lines, not fc-match.
- New font → `shared/fonts.py` + `SUBTITLE_FONTS`/`SUBTITLE_FONT_PREVIEW_STACK`/`SUBTITLE_FONT_WEIGHT` + `@font-face`.
- A nested bind mount inside the read-only `frontend/html` mount can't be created (container fails to start).

## Incident during this task
Recreating the frontend with the fonts mount at `/usr/share/nginx/html/fonts` failed (read-only parent), then a bad
`sed` corrupted docker-compose.yml; `:80` was down ~2 min until compose was restored from git and the mount moved.
Other containers were unaffected.

## Verification
- All 17 catalog fonts through the real `make_ass()` + ffmpeg `ass=`: fontselect picked the right file for each;
  variable fonts the right named instance (Montserrat 900/800/700, Inter 900/700, Oswald 700); display fonts request
  weight 400 with Bold=0. Contact sheet inspected: 17 distinct faces, 🔥 stripped from "GILA 🔥 COMEBACK!".
- word_pop/bounce ASS: one event per word, base values set before each `\t`.
- Playwright: 17 options styled in their own face/weight; selecting Anton/Montserrat loads `/fonts/…` (200); no
  console errors. Trace: Apply → PATCH `subtitle_font:"Anton"` → `jobs.subtitle_font=Anton` → preview ASS
  `Style: Default,Anton,28,0` → frame shows Anton.
- NOT verified: a final (1080x1920) render with a display font; `ui-preview` (:8081) 404s /fonts/ by design.
