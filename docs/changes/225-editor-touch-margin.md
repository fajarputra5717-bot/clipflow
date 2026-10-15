# 225 — Phone Editor: keyword swatches and switches really get ≥ 44 px tap areas

Lane C (qa 79276bb Medium, re-measured in qa 06aee4a). At 390 the Editor's small controls had invisible ::before/::after
hit areas that were meant to be 44 px, but:
- **Swatches** (26 px with a 2 px border): `inset` counts from the padding box (inside the border), so −9 px gave
  22 + 18 = 40 px; and editor.css's `.ed-swatches{gap:12px}` (loaded after index.html) overrode the phone gap, so
  neighbouring areas overlapped (Lane C measured 37.8 × 42.5). Now `inset:-12px -11px` → 44 × 46, and
  `.ed-page .ed-swatches{gap:20px;padding:10px}` (46 px between centres; the padding keeps the areas from being clipped
  by the panel or covered by the next row).
- **Switches** (42 × 26, no border): 44 × 46 (`inset:-10px -1px`).
- **Trim handles: NOT fixed here** (measured: Clip start 23 px, Clip end 32 px wide; main the same). #edTlInner clips
  everything past the clip's ends, so half of each handle and its hit area are cut off; leaning the area inward far
  enough steals timeline scrubbing (editor.spec failed). Handed to Lane B (timeline owner) for a layout fix.
Horizontal areas wider than 44 poke past the page at the right edge (1 px horizontal scroll), so extras are vertical.

touch.spec "phone Editor: swatches and switches answer a tap 21 px from their centre" scrolls each control into view and
probes with elementFromPoint (it fails on main for the swatches); it measures and reports the trim handles.
