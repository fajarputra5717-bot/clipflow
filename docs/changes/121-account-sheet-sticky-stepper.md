# 121 · Account sheet (change password, sign out); stepper sticks under the toolbar; selects match the mockup · index.html, app/auth.py

- **Account sheet** (`#accountSheet`, opened by the username in the sidebar foot, `data-account`): "Signed in as
  … · Admin/Member", change password (current + new + confirm; inline errors for empty current, < 12 chars,
  mismatch, unchanged, and the server's own message; success clears the form and says other devices were signed
  out) and Sign out (secondary). `PASSWORD_MIN_LEN` 10 → 12 (server + `PASSWORD_MIN` in the UI). Part 5 adds the
  admin "Users" section to Settings.
- **Stepper cut off (owner screenshot, v2.1117 dark):** scrolling slid `#flowNav` under the sticky toolbar, hiding
  dots + titles first. It is now `position:sticky; top:56px` (top-level nav stays whole) and compacts (32 px dots,
  no sub-lines) while the toolbar is collapsed: CSS `body:has(.toolbar.is-collapsed)`, no new scroll driver.
- **Selects** (Campaign and every other): `appearance:none` + the mockup's input box and an SVG chevron, set after
  the `[data-theme]` background shorthands so it survives dark + focus.

**Verified:** screenshots dark/light desktop + mobile (stepper fully below the toolbar when scrolled; chevron);
live `/api/auth/password` with an 11-char password → 400; harness 42 passed (+ account.spec: validation, server
error, success, stepper-below-toolbar check).
