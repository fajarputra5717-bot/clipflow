# 178 · Lane B's Review/Editor CSS on /ui/tokens.css (2026-10-09)

- editor/editor.css: font sizes 10–12 px → `--fs-small`, 13–15 → `--fs-base`, 20–24 → `--fs-h1`; 32 px control
  min-heights → `--control-h` (44 on phones), 24 px → `--chip-h`. `--ed-top` (= top bar height) already drives the
  sticky player. tokens.css is linked by index.html, which hosts both pages. editor + review specs: 68 passed.
- Lane B: new CSS uses the tokens (no px literals for type/control sizes); merge main into lane-b before editing editor.css.
