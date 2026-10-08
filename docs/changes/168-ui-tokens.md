# 168 · shared/ui/tokens.css — one token file for every page (2026-10-09)

- `shared/ui/tokens.css`, served by nginx at `/ui/tokens.css` (compose mounts `./shared/ui` read-only into the frontend;
  `location /ui/`, no-cache). Link it before a page's own CSS.
- Tokens: type `--fs-base` 14 / `--fs-small` 12 / `--fs-h1` 20 / `--fs-h2` 16; controls `--control-h` 32 (44 on
  ≤ 600 px), `--chip-h` 24, `--hit` 44; radius `--r-sm/md/lg/pill`; spacing `--s-1..5` = 4/8/12/16/24; shell
  `--appbar-h` 48, `--pill-btn` 36 (44 phone), `--pill-icon` 24, `--ed-top` = the top bar height (Lane B's sticky
  editor video).
- Colours stay in each page's theme blocks for now. Shell v2 (top bar + stepper pill) follows as 169.
