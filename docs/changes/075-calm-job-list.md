# 075 · Job list section + "only what's working moves" · index.html · v2.1116

- `#currentJobs` moved out of the import panel into `.jobs-section` (24 px below it) with a muted
  "Active jobs · N" label (`#jobsLabel`, hidden at 0, count set in `syncCurrentJobs`); cards 16 px apart.
- Card motion: removed the sweeping top border, the processing border glow, the dot glow/pulse,
  the bar's `flow` gradient and the badge shimmer inside job cards. Card classes are now
  `is-running` / `is-idle` (from `badgeClass`). Only `is-running` animates: one low-contrast
  `barSheen` (2 s) on its bar fill and a `dotBreathe` opacity pulse. Queued = static. Reduced motion: none.
- Island: `islandItems()` puts running work first (a queued job no longer leads while another runs);
  `.island.is-idle` freezes the lead spinner into a static empty ring.
- Fixed a pre-existing 9 px horizontal scroll ≤760 px: `.toolbar` bled 16 px into a 7 px container margin.

Verified (headless Chromium, 2 queued + 1 processing, light/dark × 1280/800/390): running animations =
`barSheen` + `dotBreathe` on the processing card only; reduced motion = none; gaps 24/8/16/16 px;
no horizontal scroll at any width; queued-only → island `is-idle`, no running animations.
