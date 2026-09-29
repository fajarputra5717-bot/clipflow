# 071 — Watermark library: checkerboard tiles, spring ✓, drag-and-drop, delete with undo
Date: 2026-09-29 · Commit: see `git log --grep "071"` · Files: frontend/html/index.html · UI v2.1107

## What changed
- **Tiles:** a grid (`minmax(150px,1fr)`) of `.wm-tile`. Each is a 44 px+ `button.wm-select` (`aria-pressed`) with a
  16:10 **checkerboard** preview (`--checker-a/b` per theme, image `object-fit:contain`, inset 12 px) and the
  filename. Clicking a tile selects it: **optimistic** (the ✓ moves at once), reverted with a toast if the API fails.
- **Selected state:** an accent outline and a ✓ badge that springs in (`--ease-spring`). It pops only on a change
  (`.pop` when the active id changes).
- **Delete with undo:** a trash icon (36 px + extended hit area; shown on hover/focus, always shown on touch) fades
  and scales the tile out. It is hidden locally, and a toast offers **Undo** for 5 s. The `DELETE` is sent only when
  the toast expires, or on `pagehide` via `keepalive`. Undo cancels it, so no request is made.
  This replaces `confirm()`.
- **Drag-and-drop zone:** a dashed zone with an upload glyph; the "choose a file" label keeps
  `#watermarkUploadInput` and is keyboard-activatable. While a file is dragged over it, it gets an accent border,
  tint and a slight spring scale. A drop uploads through the same `uploadWatermarkAsset()` after a client-side
  PNG/WebP check. Files dropped elsewhere in the open sheet are swallowed, so they don't navigate away.
- **Toast** (`#toast`, `role=status`, above sheets): one at a time, optional action button, slides up with a spring.
  It also replaces the `alert()`s on upload/activate/delete errors.
- Removed the old `.watermark-*` rules.
- **Global fix:** a legacy `button{border-radius:980px!important;border:…!important}` rule silently overrode
  **every** component's own radius and border. The 068 nav rows and icon buttons were pills with a faint border in
  light mode, and these tiles rendered as ovals. The two `!important`s are dropped, so component shapes apply.
  The main views were re-checked by screenshot.

## Verification (headless Chromium, :8081, /api mocked; light/dark × 1280/800/390)
0 errors. No clickability failures with the sheet open. In each size and theme:
- Selecting wm-b calls `/activate` and gives `aria-pressed=true` plus `.pop`.
- Deleting wm-a removes the tile and shows the toast "Deleted “clipflow.png”."; Undo restores it with 0 DELETE calls.
- Deleting again and waiting 5.5 s sends exactly one DELETE (wm-a), and the toast hides.
- A synthetic dragenter gives `.is-over`. A synthetic drop of a PNG sends 1 POST, the new tile appears and the highlight clears.
- Under reduced motion, 0 running animations for open, select and delete (the tile removal skips its 200 ms fade).
