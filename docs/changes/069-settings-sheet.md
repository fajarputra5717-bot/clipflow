# 069 — Settings sheet: inset lists, search, secret reveal, inline save state
Date: 2026-09-29 · Commit: see `git log --grep "069"` · Files: frontend/html/index.html · UI v2.1107

## What changed
- The Settings sheet (068) now looks like macOS System Settings. There are **8 grouped inset lists** with
  sentence-case titles ("AI & transcription", "Face detection", "Clips & rendering", YouTube, TikTok, Instagram,
  Submagic, Publishing). Each row is 44 px: a human label, then a sub-line with the `KEY` and its source (Saved / From
  .env / Default / Not set), and the field on the right. Rows stack on ≤600 px.
- **Search** (`#settingsSearch`, sticky under the title) filters rows by label, key or group. Empty groups hide,
  and a "No settings match" line shows.
- **Secret fields** (`KEY|TOKEN|SECRET|PASSWORD`, same rule as before) are `password` inputs with an eye toggle
  (`[data-reveal]`, `aria-pressed`, label flips Show/Hide). Every row reserves that slot so the fields line up.
- **Sticky footer** (material): a live "N unsaved changes" status and Reload. Save is primary and disabled while
  nothing changed. Changed rows get a light accent tint. Save goes spinner (`setBusy`) → green **✓ Saved** (spring
  pop) → back to Save. A failure shows inline in the footer instead of an `alert()`.
- **Same fields, same save rule:** `changedSettings()` is the old inline filter (non-empty, not the mask, different
  from the effective value), and only those keys go in the `PUT`.

## Decisions & trade-offs
- Group lists are always expanded, with search instead of disclosures: 32 fields is a small list, and search beats
  opening 8 disclosures.
- Save disabled with no changes is the only behavioural difference. Before, it sent an empty `PUT`.

## Verification (headless Chromium, :8081, /api mocked; light/dark × 1280/800/390)
0 errors. No clickability failures with the sheet open. In each size and theme:
- Save starts disabled. "token" shows exactly the 3 token rows, and "zzz" shows the no-match line.
- Editing CLIP_COUNT gives "1 unsaved change" and enables Save. Reveal switches the Gemini key to `text`.
- Save goes Saving… → ✓ Saved. The PUT body is exactly `{"values":{"CLIP_COUNT":"7"}}`. It returns to Save
  (disabled), and Esc closes.
- Under reduced motion, 0 running animations for open, type and save.
