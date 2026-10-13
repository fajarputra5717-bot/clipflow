# 213 · Shimmer/glow animations on transform + opacity only (deep audit L8, 2026-10-14)

Lane C's CSSOM scan listed 8 keyframes animating `background-position` / `box-shadow` (repaint every frame):
- `badgeShimmer` (.badge.running::after), `shimmer` (.queue-thumb:empty skeleton, now on its ::after), `aiShine`
  (.ai-highlight:after): a fixed gradient on a pseudo-element slides with `transform: translateX(-100% → 100%)` inside the
  element's `overflow:hidden` (same look).
- `aiGlow` (.ai-highlight): the outer box-shadow pulse is now an `opacity` pulse of an inner glow ring on `::before`
  (an outer glow on a pseudo-element would be clipped by the button's overflow:hidden); the button keeps a static
  soft shadow + 1 px purple ring.
- `analyzeGlow`, `shine`, `sweep`, `flow`: no rule used them; deleted.
No keyframe animates background-position or box-shadow any more. Reduced motion: the global rule (`*, *:before,
*:after { animation: none }`) covers the moved pseudo-elements. UI 254 passed.
