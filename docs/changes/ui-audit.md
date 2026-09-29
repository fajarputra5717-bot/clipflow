# UI audit (R-13 / TASKS-UI-QA T1)
Date: 2026-09-29 · Base: UI v2.1102 (after R-12 sidebar) · File: frontend/html/index.html

This is an inventory taken before any R-13 fixes. The method: a script parses every CSS rule's `transition`/`animation`,
plus a grep of the render functions. Line numbers are v2.1102. **Fixed in R-13** marks what R-13 itself changes. The
rest is left for the QA tasks that own it (T4–T7 → REBUILD R-11 / TASKS-4-UIUX).

## 1. Interactive affordances (collapse/expand and pickers)

| Affordance | Treatment today | Inconsistency |
|---|---|---|
| Sidebar hide (`.sidebar-collapse`, R-12) | 18 px sidebar icon, 32 px hit box, `aria-expanded` | A distinct action (hides a panel), which is allowed; matches the chevron's size and colour |
| Import "Options" (`#importOptions`, R-12) | trailing 16 px chevron, rotates 180° over 200 ms, whole row is the hit target | This is the target pattern |
| Settings disclosures (`.settings summary:after`) | `＋` / `−` glyph **swap**, float right, no animation, no `aria-expanded` (native `<details>`) | Different glyph; swapping instead of rotating (T5) |
| Settings groups (AI / FACE / …, rendered by `loadSettings`) | same `＋/−` swap | same (T5) |
| Version history (`details.version-history`) | browser-default `▸` marker on the **leading** edge | Third style, wrong edge (T5) |
| Candidate Edit (`[data-edit]`) | regular pill button that toggles the drawer, no `aria-expanded` | A button, not a disclosure; missing state (T7) |
| Thumbnail picker (`.thumb-option`) | card with a check badge and a `thumbSelectPop` animation | Fine; `alt` text not audited per image (T7) |
| Tabs (`.tab`) | `<div>` with **no tabindex/role** | Not keyboard reachable at all (T7, high) |
| Floating logo chip (`#topbarLogo`) | `role=button tabindex=0`, Enter/Space handled | OK |

## 2. Transitions and animations

The 164 declarations were parsed. Only the flagged ones are listed.

**Animating layout properties (relayout every frame):**

| Selector | Properties | Duration | Notes |
|---|---|---|---|
| `.topbar` | gap, margin | 500 ms | pill cluster, **fixed in R-13** |
| `.tabs` | max-width, padding, gap, border-radius | 500 ms | the pill morph, **fixed in R-13** |
| `.tab` (condensed) | padding and font-size change with no transition, so the text reflows mid-morph | — | **fixed in R-13** |
| `.tab-indicator` | width | 500 ms | **fixed in R-13** (scaleX) |
| `.job-island` | width (JS-measured FLIP), max/min-width, padding, border-radius | 500 ms | **fixed in R-13** (rewritten) |
| `.job-island-bar` | width | 800 ms | also out of range, **fixed in R-13** (scaleX) |
| `.topbar-logo`, `.topbar-logo-text` | max-width, padding, gap | 400 ms | T2-adjacent, left (a hover reveal; not on the scroll path) |
| `.theme-toggle-float` | right | 500 ms | same, left |
| `.mini-bar-fill` | width | 600 ms | job-card progress, R-11 |
| `.edit-drawer` | max-height, margin-top | 450/350 ms | R-11 |
| `.caption-preview-text` | font-size, letter-spacing, gap | 250 ms | this mirrors the ASS output, so it is intended |

**Duration outside 100–500 ms:** `.job-island-bar` 800 ms, `.mini-bar-fill` 600 ms, `.progress-ring-bar` 900 ms,
`@viewSwitchIn` 550 ms. The looping ambient animations (pulse, flow, shimmer, glow: 1.3–3.4 s) are exempt; they are
not transitions.

**`transition: all`:** none.

**Default `ease`:** about 35 declarations, all on colour, opacity, box-shadow or filter fades (e.g. `.job-island` opacity,
`.view-section` filter, `.job-overlay` filter). That is acceptable for fades. It is low severity, not changed.

**Two scroll drivers for one state (the reported conflict):** `initHeaderCondense` (an IntersectionObserver on
`#headerSentinel`, zero hysteresis) toggles `.condensed`. A `transitionend` listener on `.tabs` then re-measures the
indicator, and `freezeUnderHeader()` scrolls programmatically while the observer fires. **Fixed in R-13**: one
rAF-throttled scroll handler with hysteresis owns `.condensed`.

## 3. Status badges (`stageLabel()` / `badgeClass()` / `.badge.*`)

| Class | States mapped | Colour | Contrast light / dark (text on tinted fill) |
|---|---|---|---|
| running | queued, processing, downloading, transcribing, analyzing, preview_*, render_queued, rendering, thumbnail_*, **partial_failure**, anything unknown | blue #0071e3 | 4.22 / **2.97** |
| review | review | amber #c76a00 | **3.52** / **3.64** |
| completed | completed | green #1a8f47 | **3.77** / **3.36** |
| failed | failed | red #d70015 | 4.76 / **2.59** |
| cancelled | cancelled | grey #6e6e73 | 4.57 / **2.75** |

- **Semantic collision:** `partial_failure` is rendered blue as "in progress". It should be amber (needs attention).
- **Queued vs running:** both are blue; idle "Queued" should be neutral grey per T6.
- **Contrast:** 7 of 10 combinations fail WCAG AA (4.5:1 for the ~10 px text). Dark mode is worst: the badge fill is
  overridden to white 7 %, but the text keeps its light-theme colour.
- **Labels:** "Thumbnail queue" (should be "Thumbnail queued"). The `||s` fallback prints raw enums for unknown states.
- → T6 (R-11 / TASKS-4-UIUX). Not fixed in R-13.

## 4. State coverage per component

| Component | Loading | Empty | Error | Disabled |
|---|---|---|---|---|
| Import job list (`#currentJobs`) | **none** (blank until the first response) | "No active jobs." | `.error-box` | n/a |
| Publish list (`#queueJobs`) | **none** | "No jobs in Publish yet." | `.error-box` | n/a |
| Job-card thumbnails (`.queue-thumb`) | shimmer on `:empty` | **same grey shimmer forever** | **none** | — (T4) |
| Candidate preview | — | "Preview is not ready yet." | **none** (video error unhandled) | — |
| Version history | "Loading…" | yes | yes | — |
| Settings panel | **none** | — | alert() | — |
| Watermark library | **none** | yes | alert() | upload label `aria-disabled` |
| AI action buttons (typo/hook/description) | ad-hoc label swap ("Working…", "Writing…", "Generating…") | — | alert() | `disabled` |
| Analyze | `.analyze-ready` glow when valid | — | status box | `disabled` |
| Job island | n/a | hidden | **none** (poll errors only logged) | — |

## 5. Focus states

- There is no global `:focus-visible` rule. Buttons and `role=button` choices rely on the UA default ring (not removed,
  so they are visible). The only custom ones are on `.topbar-logo` and the inputs.
- `outline:none` on `input,select,textarea` (l.420) **has** a replacement (`:focus` border and 4 px ring), so that is OK.
- `.tab` elements cannot receive focus at all (see §1).
- `.job-island` is a `<button>` but has no `aria-live`, so progress is not announced. **Fixed in R-13** (`role=status`
  text).
- `.sidebar-collapse` / `.sidebar-open-btn` / Options summary use the UA ring (R-12).
