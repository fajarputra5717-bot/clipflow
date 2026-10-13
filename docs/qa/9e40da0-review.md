# lane-b 9e40da0 (timeline keys) + 52ca661, 516c108, daf82a9 — staging :8080

## 9e40da0 — timeline keyboard (closes my audit Low)
- PASS: `#edTlInner` has `tabindex=0`, `role=group`, an aria-label that lists the keys, and `aria-keyshortcuts` = Space, ArrowLeft/Right, Shift+Arrow, Home, End. Focus ring visible when focused.
- PASS: focused on the timeline, measured on the video: → +0.1 s (5 → 5.1), Shift+→ +1 s, ← −0.1 s, Home → 0, End → 33.76 s (end), Space plays, Space pauses.
- PASS: Home with focus on the play button does not move the video (7 → 7); in the caption text box Home and Space do not touch the video (stays 7 s, paused). 0 page errors. The zoom slider guard is Lane B's spec; I did not repeat it.
- Low: the timeline is the 72nd Tab stop at 1280×800 (every keyword chip and inspector control comes first). A keyboard user can reach it, but slowly; consider putting it earlier in the order or giving it an access key / skip link.

## 52ca661 (my e82389e Low) — PASS
At 768×1024 the keyword box is 56 px with 58 px of content: hint hidden, no `more-end` fade. 390 (192/242) and 1280 (112/142) still show the hint and the fade. Note 52ca661 alone has a red spec until 516c108 (test-only follow-up): bisect-unfriendly; squash or reorder when merging.

## daf82a9 (Lane B's own bug in 434f6bc) — PASS
Phone, scrub bar at the end (video at 33.79 s, then a tap on the bar's right edge → 33.81 s, `scaleX(1)`, knob `translateX(100%)`): `scrollWidth` stays 390 (= innerWidth), `body.scrollWidth` 390; before the fix it was 541.

## Not verified
Zoom-slider key guard on the timeline page (Lane B's spec), screen-reader announcements for the timeline group, real touch.

Merge: OK for 9e40da0, 52ca661, 516c108 and daf82a9 (with the editor items already reviewed; the small-video Medium from 44e7847 is still the owner's decision).
