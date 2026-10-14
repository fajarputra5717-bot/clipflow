# lane-b 4ab7884 (draggable video/timeline split) + 0df6fb8 (word chips = one Tab stop) — staging :8080

Measured on my lane-c-a clip. (Staging has the 22 px test banner; production has 22 px more height.)

## 4ab7884 — split (closes the small-video Medium)
- PASS sizes (video w×h → page scroll): 1280×700 210×374 (was 188×334), no page scroll; 1280×800 244×434 (was 169×300), no scroll; 1440×900 256×455 (was 225×400), no scroll; 1280×640 177×314, no scroll (the no-scroll layout now starts at 640 px tall); 1280×600 and 390×844 keep the scrolling layout (separator `display:none`, not focusable); no horizontal overflow, 0 page errors at all sizes.
- PASS separator: `role=separator`, `tabindex=0`, `aria-valuenow` (video share, 86 at 1280×800) and `aria-valuetext` "Video 434 px tall, timeline 72 px". Keys: ↑ video −16 (434→418), Shift+↑ −64 (→354), ↓ +16 (→370), End → smallest timeline (video 434, timeline 72), Home → biggest timeline (video 200, timeline 306). Limits held: timeline ≥ 72, video ≥ 200.
- PASS drag: from default, dragging the line up 150 px → video 278 / timeline 228; dragging far down stops at 434/72; the position is stored per user (`clipflow_editor_split_<user id>=306`) and survives a reload.
- Note (design): at the default 72 px the timeline shows only buttons, ruler and waveform; the word/pause chip row (the cut tool) is below the visible area until the user drags the line up, at every desktop size. Fine as the owner chose, but a first-time user may not find the words; consider remembering "open" for users who cut, or a one-line hint ("drag ⋯ up to see words").
- Not verified: touch drag of the line (hidden in the phone layout), the 455 px default on production (no banner), dark theme look.

## 0df6fb8 — chips are one Tab stop
- PASS: from the play button the timeline is the 11th stop (10th at 390), the first inspector tab the 20th (19th at 1280×700, 18th at 390) and Render preview the 76th/75th/74th (was 67th and 123rd): matches Lane B's 21st/76th within one.
- PASS roving group: exactly one chip has `tabindex=0`; ←/→ walk in time order (pause 0.4 s → "Ngapain?" → pause 2.8 s → "Ngapain?"; ← goes back); End → last word ("Oh"), Home → first; arrows on a chip leave the video time alone (3.14 → 3.14); Enter seeks (video to 33.38 s); Space does not play; one Tab leaves the group (next stop is the trim handle); Shift+Tab returns to the remembered chip. 0 page errors.
- Low: the first chip is the 16th press from the play button, because the timeline toolbar buttons and trim handles come before it. Fine.

## Findings
- None blocking. The 1280×700 aside is resolved (210×374).

Merge: OK for 4ab7884 and 0df6fb8.
