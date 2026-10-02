# 106 · UI shell (P1 task 0, part a): the flow-preview stepper is the top-level navigation · index.html, tests/ui, CLAUDE.md

**Decision.** `flow-preview.html` is the UI/UX spec for the whole app (mapping in docs/roadmap.md).

**Now.**
- `#flowNav` stepper card at the top of the content column, 8 steps from the mockup (`FLOW_STEPS`, same
  icons, connectors, active/done states; horizontal scroll ≤ 600 px):
  Analyze → the Import view (`data-nav="current"`), Review → the job list/detail (`data-nav="queue"`, the old
  "Publish" view), Editor → opens the visible job's first clip editor (or scrolls to the open one); disabled
  "Open a clip in Review" until a job detail is open. Campaign / Auto-import / Track: disabled "Coming in P3";
  Schedule / Publish: disabled "Coming in P2". No mock content.
- `#pageTitle` follows the active step (Analyze / Review / Editor). The view formerly called "Publish" is now
  Review everywhere (title, empty state, status texts); "Publish" is reserved for P2.
- Sidebar: tools only (Watermarks, Settings, theme); its indicator hides when no sidebar item is current.
  Gear button in the toolbar opens Settings. Bottom tab bar: Analyze / Review / Watermarks / Settings.
- Island untouched.

**Verified:** headless at 1280 light / 390 dark (Analyze → Review → job → Editor opens the drawer, titles
follow, disabled steps show their phase, gear opens Settings, no console errors); UI harness 24/24 with the new
`shell.spec.js` and `jobs.spec.js` updated to "Review".
