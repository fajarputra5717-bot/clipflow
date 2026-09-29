# ClipFlow — UI QA/QC pass

Act as a QA/QC engineer, not a feature developer. The job is to find
and fix defects and inconsistencies, **not** to add capability. If you
find yourself designing something new, stop — that's out of scope.

Read `CLAUDE.md` and `docs/changes/INDEX.md` first, plus
`016-dynamic-island-header.md` (the pill/island work being revised
here). Same ground rules: one commit per task, `docs/changes/NNN` +
INDEX line, compile checks, honest verification notes.

**Context that matters:** the dynamic-island work shipped without any
real-browser verification (no browser automation in the environment;
jsdom + code tracing only). The motion problems in Task 2 below are
exactly the class of defect that gap would hide. Treat the previous
implementation as unverified, not as a correct baseline.

---

## Task 1 — Audit before fixing (deliverable: a written report)

Produce `docs/changes/ui-audit.md` before changing code. Inventory,
don't guess. Grep the CSS and the render functions and list, in
tables:

1. **Every interactive affordance** and its current visual treatment —
   sidebar collapse (`‹`), settings disclosures (`+`), the Options
   disclosure (`⌄`), version history (`<details>` default marker),
   candidate Edit, thumbnail pickers. Flag every inconsistency.
2. **Every transition/animation** — selector, property animated,
   duration, easing. Flag: anything animating a layout property
   (`width`, `height`, `top`, `margin`) instead of `transform`/
   `opacity`; any `transition: all`; any duration outside 100–500ms;
   any default `ease`/linear where a considered curve belongs.
3. **Every status badge string and colour** — `stageLabel()` /
   `badgeClass()` and their CSS. Flag semantic collisions (two
   different states sharing a colour) and any label that isn't plain
   language.
4. **State coverage per component** — does each have a defined
   loading, empty, error, and disabled state, or does it just render
   nothing? List the gaps.
5. **Focus states** — anything interactive with no visible
   `:focus-visible`, and any `outline: none` without a replacement.

Report findings first. Then fix in the tasks below.

---

## Task 2 — The pill motion feels wrong (highest priority)

The morph reads as mechanical rather than natural. Diagnose against
this list before rewriting — several are likely true at once:

- **Layout properties animating.** If `width`, `padding`, `height` or
  `top` are in a transition, the browser relayouts every frame — that
  is the classic "unnatural" feel. Everything visual should move via
  `transform: scale()/translate()` and `opacity` only.
- **`backdrop-filter` during transform.** Glass surfaces re-rasterize
  each frame while transforming, which stutters. Test whether pinning
  `will-change: transform` (and *only* during the transition, removed
  after) fixes it; if the blur itself is the cost, reduce blur radius
  during motion and restore it on settle.
- **Content reflow mid-morph.** If children reflow while the container
  resizes, it will never look clean. Children should cross-fade and be
  positioned absolutely during the transition, not reflow.
- **Hysteresis too wide.** 96px collapse / 56px expand is a 40px gap —
  it may read as laggy on a short scroll. Test 72/56 and 64/48.
- **One duration for asymmetric motions.** Collapse and expand usually
  want different timings; expanding should feel slightly faster.
- **The easing itself.** `cubic-bezier(.32,.72,0,1)` is a reasonable
  ease-out, but a shape morph often wants a subtle spring with a
  small overshoot. Try it both ways and keep what looks right.

**Verify visually.** If no browser automation exists, say so, and
produce a minimal standalone HTML repro of just the pill so a human
can judge the feel in one click. Don't claim it's fixed on the basis
of code reading.

---

## Task 3 — Give the job island its own bar (reverses part of task B)

Merging the tab switcher and job status into one pill was my call and
it was wrong in practice — reverse it. They're different things: tabs
are navigation and always present; job status is transient and
informational. Sharing one capsule makes both feel unstable as the
content changes underneath them.

- Tabs pill: its own element, constant size, morphs only on scroll.
- Job status island: its own separate bar/capsule, appearing only
  when a job is running, with its own entrance/exit transition.
- Position them so they never collide at any viewport width, including
  when both are visible and the job title is long.
- The job island shows real progress (stage + percent), not just a
  label. It should animate its own progress smoothly, independent of
  the tabs pill.
- Keep the changelog honest: note that this reverses the merge in
  `016-dynamic-island-header.md` and why.

---

## Task 4 — Job cards show placeholders instead of thumbnails

Every job card in the Publish/queue list shows an empty grey
rectangle where a preview should be. Diagnose first:

- Does the job-list API response include candidate thumbnail paths at
  all? `list_jobs` may not be selecting them, in which case the
  frontend has nothing to render and the placeholder is correct
  behavior for missing data.
- If the data is there, is the `<img>` src wrong, 404ing, or being
  built from an absolute disk path instead of the served URL?
  Check the Network tab.

Then fix so each job card shows its candidates' actual thumbnails:

- Show a small thumbnail per candidate (2 candidates → 2 thumbnails),
  so the card previews what's inside without opening it.
- Lazy-load (`loading="lazy"`) — the queue can get long.
- Real states: skeleton shimmer while loading, a labelled placeholder
  when a candidate genuinely has no thumbnail yet ("Rendering…"), and
  a broken-image fallback. Not a bare grey box for all three.
- Hovering a thumbnail may show the preview video muted-autoplay, but
  only if it doesn't hurt scroll performance — measure, and drop it if
  it does.

---

## Task 5 — One collapse/expand affordance everywhere

Right now there are at least three: `‹` (sidebar), `+` (settings
sections), `⌄` (Options). Pick one and apply it consistently.

- Use the platform-conventional chevron: `⌄` pointing down when
  collapsed, rotating 180° to `⌃` when expanded. Rotation animates
  (~200ms) rather than swapping glyphs — swapping is what makes it
  feel cheap.
- Same size, same colour, same hit target, same position (trailing
  edge) in every instance.
- Whole header row is the hit target, not just the icon.
- `aria-expanded` on every one of them.
- The sidebar collapse is a different action (hide a panel, not
  disclose content) — it may keep a distinct icon, but must match in
  size, weight and colour.

---

## Task 6 — Status badges

`Completed`, `Ready for review`, etc. currently read as generic web
chips.

- Colour semantically and consistently: neutral/grey for idle,
  blue for in-progress, amber for needs-attention, green for done,
  red for failed. Audit for two states sharing a colour.
- Use SF-style subtle fills (tinted background + matching text) rather
  than saturated blocks.
- In-progress badges get a subtle indeterminate shimmer so "working"
  is legible at a glance without reading.
- Check contrast in both light and dark themes — the current amber on
  dark may fail WCAG AA. Measure, don't eyeball.
- Keep labels plain: "Ready for review" is good; anything mirroring an
  internal status enum (`preview_queued`) is not.

---

## Task 7 — Accessibility sweep

From the Task 1 audit findings:

- Visible `:focus-visible` on every interactive element; no bare
  `outline: none`.
- Keyboard: tab order follows visual order; Escape closes the mobile
  sidebar drawer and any open disclosure; Enter/Space activate every
  custom `div`-as-button.
- `aria-expanded`, `aria-controls`, `aria-live` on the job status
  island so progress is announced.
- `alt` text on thumbnails.
- Verify the `prefers-reduced-motion` path actually holds after tasks
  2 and 3 — a universal `transition: none !important` rule can be
  defeated by inline styles or JS-driven animation.

---

## Order

Task 1 (audit) → 2 (motion) → 3 (island) → 4 (thumbnails) →
5 (affordances) → 6 (badges) → 7 (a11y).

Tasks 2–4 are the ones that will visibly change how the app feels.
5–7 are consistency and correctness. Do not skip Task 1 — the point
of a QA pass is that the findings drive the fixes, not the reverse.
