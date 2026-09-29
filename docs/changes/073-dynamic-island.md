# 073 — Dynamic Island, Apple-style (springs, split, ready/failed events)
Date: 2026-09-29 · Commit: see `git log --grep "073"` · Files: frontend/html/index.html, docs/ui-recordings/073-*.webm, CLAUDE.md · UI v2.1107

## What changed
- **Old island removed:** the translucent top-left capsule and its CSS. The "R" avatar chip was already removed in 072.
  The new `#island` sits **outside the app shell**: `position:fixed`, 8 px from the top, centred, `z-index:1000`,
  pure black `#000` in both themes with `inset 0 0 0 1px rgba(255,255,255,.08)`, white text.
- **Not rendered while idle** (`hidden`). When a job starts it is born as a 12 px pill and **springs** open to
  compact size with a slight overshoot. The content layer fades in 60 ms later.
- **Compact** (h 36): leading 20 px YouTube thumbnail (spinner fallback), truncated title, trailing progress **ring**.
  The ring's `stroke-dashoffset` transition is 2 200 ms linear, one poll interval, so it glides between polls and
  never jumps.
- **Expanded** (hover with a 120 ms intent delay; click/Enter to pin; tap on touch): springs to ≤380 px, radius 28.
  It shows title, stage, % and a linear bar, plus **Cancel**, which is shown only if a global `cancelJob(jobId)`
  exists (none in this branch; Lane A's wiring will light it up). The size morph starts first. Content cross-fades,
  then head / bar / actions stagger in at 60/100/140 ms. Clicking outside, pressing Esc or moving the mouse away
  collapses it.
- **Split island:** with more than 1 task, a detached 36 px "+N" circle springs out beside the compact island (it
  opens the existing running-jobs overlay, now hung under the island). It merges back while expanded, so the shape
  stays centred and fits a 390 px screen.
- **Events:**
  - A job going from busy to review/completed triggers a **✓ Ready for review** auto-expand: green check pop,
    green bar at 100%, for 2.5 s. It then collapses to the next job, or disappears.
  - A job going to failed/partial_failure gives a **red tint** and a "Failed · <stage>" expand for 2.5 s. It then
    stays compact and red until seen (hover or click).
  - If a job disappears from the running list, its final status is fetched once.
- **Physics:** `springEasing(stiffness, damping)` integrates a damped oscillator and emits CSS `linear()` easing
  sampled at 60 Hz. There are three presets: grow (260/20, overshoot), settle (300/34, no wobble) and pop. Size
  uses FLIP-style *measure first → set last → animate* with WAAPI on width/height/radius. The shape is an isolated
  `contain:layout paint` fixed layer, so it doesn't relayout the page. Interrupted morphs start from the live
  mid-flight size.
- **Reduced motion:** no size animation. Every mode change is a 200 ms opacity cross-fade.
- **Fixes found here:** sheets now also make the phone tab bar and the island `inert` (at 390 the tab bar stayed
  focusable behind a bottom sheet; 072 regression). The running-jobs overlay is re-anchored to the top centre.

## Decisions & trade-offs
- **Size is animated as width/height, not a `transform: scale` FLIP.** Scaling a 12 px pill to 380 px distorts the
  corner radius and any text inside. The morph layer is isolated, and the measured frame pacing (below) shows no cost.
- The island is shown on **both** views, including Import where the job card also shows progress (an OS-level
  indicator is global). Before, job-level progress hid on Import.

## Verification (headless Chromium, :8081, scripted job lifecycle on a mocked /api; light/dark × 1280/800/390)
- 0 console or page errors. No clickability failures in any state.
- Every run gives the same sequence: hidden when idle → compact 248×36 (150×36 at 390) centred on the viewport →
  hover/tap expanded 380×83 (374 at 390), radius 28 → Esc back to compact → "+1" split → ✓ ready (centred, split merged)
  → back to compact on the next job → red failed 379×67 → red compact until clicked → hidden.
- Background `rgb(0,0,0)` in both themes (failed tint `rgb(42,7,6)`).
- **Frame pacing** during the birth spring and the hover-expand spring, from rAF deltas over 700 ms: **60 fps
  average, worst frame 16.8 ms, 0 frames over 20 ms**, in all 6 runs. Measured in headless Chromium on this VM
  (software rendering); a real GPU should be at least this good.
- Reduced motion: only `opacity` animations run (no width/height/radius).
- Regression: 068/070/071/072 scenarios re-run, all clean.

Recordings (1280 and 390, light + dark): nothing running → job starts → ring glides → hover/tap expand → collapse →
second job splits off → first job ready (✓, auto-collapse) → failure (red) → seen → gone.
`docs/ui-recordings/073-dynamic-island-{light,dark}[-390].webm`.
