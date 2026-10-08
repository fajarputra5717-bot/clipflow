# 169 · Shell v2: thin top bar + floating stepper pill, same on every page (2026-10-09)

Owner spec "Shell redesign v2" (replaces shell items 1–2). Before/after screenshots at 390 + 1280 for every step:
`CLIPFLOW_SHOTS=<label> tests/ui/run.sh specs/shots.spec.js` → docs/ui-recordings/shell-v2/<label>/ (gitignored).

- Removed: left sidebar (+ drawer, scrim, collapse state), large iOS title, sticky stepper card, ≤ 600 px tab bar,
  toolbar version popover.
- Top bar 48 px: logo · page context (campaign / job title from what's on screen, else the page name) · Watermarks,
  Settings, account menu (Account, Appearance, Refresh, What's new + version, Sign out). Phone: Watermarks + Settings
  inside the menu so the bar's centre stays free for the island.
- Stepper = floating glass pill, bottom centre, safe-area aware: 24 px icons, 36 px hit (44 on phones), only the active
  step shows its label; phones hide the two unbuilt "Coming in P3" steps (8 × 44 px + a label don't fit 390 px).
  Lifts the editor's sticky action bar; hidden while that bar has focus on phones. Island unchanged, top centre.
- `/ui/tokens.css` (168) linked first; body base 14 px.
- Tests: fixtures `nav()` goes through the menu when a tool isn't in the bar; new `openAccount()`, `menuItem()`;
  sidebar/tab-bar/popover tests replaced by account-menu and pill tests. 172 passed.
- Known (fixed next, 170): opening the Editor from Review can leave the old job list visible (two lane-b pages restore
  each other's hidden sections); Editor with no clip shows the old list (171).
