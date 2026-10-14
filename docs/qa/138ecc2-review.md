# ui-phase1 138ecc2 + 4b78963 (UI phase 1, change 222) — live on staging :8080 (frontend bind mount of /opt/clipflow-ui; backend = lane-b)

Measured as lane-c-a with Playwright at 390×844, 1280×700, 1280×800, 1440×900, light + dark, plus a git-served run of the touched specs.

## Item by item
1. **Scale ×1.2 — PASS:** body 16 px, top bar 56 px, dock buttons 48 px (44 phone), icons 24 px. No horizontal overflow and no clipped text on any of the 8 steps at 390, 1280×700, 1280×800 and 1440×900. Phone controls ≥ 44 px except the known editor colour swatches (26 px) and editor switches (42×26, hit area padded by ::before), the Auto-import switch (51×31, 53×45 hit area) and the new info buttons (24 px, hit area padded `::before{inset:-10px}` → ~44).
2. **Dock — PASS with one unmet target:**
   - 48/44 px buttons, 24 px icons; the glider is `transform: translateX()` only (left/width unchanged, 150 → 300 px across a switch, 0.45 s); tooltips (`.flow-label`) appear on hover and on keyboard focus, none at rest or after the mouse leaves; no tooltips on touch (by design).
   - Bar → pill on scroll with hysteresis: at 1280 the dock goes 408 → 359 px between scroll 40 and 80 px and stays a pill while scrolling back up until scrollY 0 (no flicker at the threshold).
   - Glass: `rgba(255,255,255,.58)` + `blur(22px) saturate(1.8)` light, `rgba(38,38,42,.55)` dark; `prefers-reduced-transparency` (CDP-emulated) → opaque `rgb(255,255,255)` panel, no backdrop-filter; `prefers-reduced-motion` → glider transition 0 s (jumps); the `@supports not (backdrop-filter)` fallback exists in CSS (not exercised).
   - Frames (headless, software compositing, 2 runs each): 20 wheel steps down and up 0 frames > 20 ms at 1280 and 390; 5 page switches at 390 0 frames > 20 ms; **at 1280, 4–6 frames > 20 ms per 5 switches (worst 33 ms = 2 frames, 0 > 34 ms)**. The owner's "0 dropped frames" is therefore not met for the desktop page switch on this box (Lane A said the same: needs real hardware).
3. **Bottom padding — PASS:** scrolled to the end, the last content text ends 61–256 px above the dock on all 7 pages at 1280×800 and 390×844 (Review 86/61, Publish 106/139, Schedule 124/109).
4. **One title — PASS:** every page has exactly one visible heading (H2 "Campaigns", "Watch source channels", "New job options", "All clips", clip title in the Editor, "Schedule", "Publish queue", "Views → earnings"); the top bar shows only logo + icons/menu (page name only as an sr-only title).
5. **Menu — PASS:** desktop menu = Account, Appearance, What's new, Sign out (no Watermarks/Settings, no Refresh; the top-bar icons remain); phone menu adds Watermarks + Settings; version is a plain label.
6. **Version — PASS:** `version.json` v3.222; menu shows "v3.222" and the latest 5 entries (222…218); `tests.test_version` OK.
7. **Switches on are blue — PASS:** editor switches `rgb(0,113,227)` light / `rgb(10,132,255)` dark = `--accent`; Auto-import `.ai-switch[aria-checked=true]` → accent in both themes (verified by forcing the attribute; none of my channels is watched).
8. **Intros + info — PASS with Lows:** each page has a one-line intro + inline info button (aria-label "More about …", aria-expanded, opens inline text). Lows: at 390 the Import and Review intros wrap to 2 lines (info icon pushes them), Analyze has no intro/info button, Escape does not close the info text (toggle only).

## 4b78963 (desktop inspector 380 → 470 px) — PASS
Editor at 1280×800, 1440×900, 1280×700, 1100×800, 1024×768, 900×800: inspector 470 px, all 6 tabs fit without the fade (last tab ends 3 px inside the row), 19 caption-preset samples, 0 clipped; no page scroll, no horizontal overflow; video 221×392 at 1280×800 (255×455 at 1440×900, 194×344 at 1280×700, 184×327 at 1024×768, 202×359 at 900×800), 0 page errors. The owner's 455 px target is still reached only at 1440×900.

## Specs
Git-served 138ecc2, specs dock, scale, shell, account, touch, island, review (desktop + mobile): 54 passed, 10 skipped, **2 failed: `dock.spec.js:18` "glider sits under the active step" (both projects)**: it expects the first step icon to be 24 px wide and got 48 in my served copy, while the live staging dock icon measures 24 px: probably my copy's CSS/asset layout, but Lane A should confirm the spec passes on a clean checkout.

## Not verified
Before/after screenshots (Lane A has the "before"; mine are after-only, in my scratchpad), real-hardware frame rates, the no-`backdrop-filter` browser path, Safari, and the Auto-import switch in its real on state.

Merge: OK for 138ecc2 and 4b78963 (Lows only; the 0-dropped-frames target is unmet on desktop page switches in software rendering).
