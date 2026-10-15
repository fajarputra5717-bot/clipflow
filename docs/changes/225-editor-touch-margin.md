# 225 — Phone Editor: tap areas with margin on swatches, switches; swatches spaced

Lane C (qa 79276bb Medium): at 390 the keyword swatches (26 px), Editor switches (42×26) and trim handles (18 px wide)
showed no hit at 22 px from their centre. They already had invisible hit areas of exactly 44 px (::before/::after in
the phone rule), so a probe at 22 px sits on the boundary; main passes the same probe at 21 px.
Now: swatches 44×46 and spaced 20 px (26 + 20 = 46 px between centres, so neighbouring hit areas don't overlap),
switches 44×46, trim handles stay 44 px wide. Wider than 44 horizontally pokes past the page at the right edge (1 px
horizontal scroll, caught by editor.spec), so the extra margin is vertical only.
touch.spec "phone Editor: swatches, switches and trim handles answer a tap 21 px from their centre" (elementFromPoint).
