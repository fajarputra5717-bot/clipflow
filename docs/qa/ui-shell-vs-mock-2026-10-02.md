# UI shell (106/107) vs flow-preview mock · early look before the P1 gate · 2026-10-02

Playwright (Chromium) at 1280×900 and 390×844, app with the harness's mocked API, mock = `flow-preview.html`.
Screens: `frames/ui-shell-106-107/app-{desktop,mobile}-analyze.png` vs `mock-{desktop,mobile}-{analyze,review,editor}.png`.
P1 task 0 is still in progress, so these are differences to close, not bugs (except where marked).

## Shell (both widths)
1. **Frame:** app keeps the left sidebar (Watermarks, Settings, Appearance) and a large page title ("Analyze");
   the mock has a slim top header (logo, "PREVIEW" pill, dark-mode toggle), no sidebar, no page title.
2. **Stepper card header:** mock shows eyebrow "PLANNED WORKFLOW", title "Campaign → post → paid", hint "Tap a step
   to jump to it"; app shows the steps only.
3. **Step subtitles (built steps):** app "Import a video / Clips + checks / Open a clip in Review" vs mock
   "Language + layout / Hooks + rule checks / Trim, captions, effects". Disabled steps "Coming in P2/P3" ✓ (as agreed).
4. **Content width:** mock content max ≈ 1090 px centred; app fills the column.
5. **Mobile:** app has the stepper AND a bottom tab bar (Analyze, Review, Watermarks, Settings): two navigations;
   mock has the stepper only. App header on mobile: sidebar toggle + gear + refresh, no logo.
6. **Low (bug) · mobile disabled steps give no reason:** `.flow-sub` is hidden ≤ 600 px, so "Campaign", "Schedule"
   … are just dimmed; "Coming in P2/P3" is invisible (no tooltip on touch). Mock shows labels only, but its steps
   are all enabled.

## Analyze step
7. Heading: mock "STEP 3 · ANALYZE / New job options / Auto-imports use these as defaults…"; app "Import a new job /
   Paste a YouTube link…".
8. Mock shows Language as an inline segmented control (Auto-detect / English / Indonesian + "Detected from the first
   30 s…") and Layout as 4 visual cards; app hides language/layout/split/platform in a collapsed "Options" row.
9. Layout choices differ in substance: mock "Gameplay + facecam / Speaker follow / Two-speaker stacked / Wide + blur";
   app "Auto / Left / Right / No facecam". (Feature gap, roadmap decides.)
10. Mock primary action "Start analysis" + duration estimate below the form; app "Analyze" beside the URL.
11. App has "Job name" (not in mock), Campaign full width (mock: Campaign + Language side by side).

Matches: stepper order/labels/icons, active-step style (blue filled dot, blue label), connector lines, card radius and
shadow, input style (12 px radius, 15 px text), primary blue, light theme tokens.

## Not compared yet
Review and Editor (mock shots taken; P1 builds them), dark theme, Settings/Watermarks sheets.
