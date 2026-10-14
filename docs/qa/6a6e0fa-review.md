# lane-b 6a6e0fa — Tab order player → timeline → inspector (staging :8080)

Measured on my lane-c-a clip (57 word chips) with real Tab presses starting from the play button.

| | 1280×800 | 1280×700 | 390×844 |
|---|---|---|---|
| timeline (`#edTlInner`) | 10th press (11th stop incl. play) | same | same |
| first inspector tab (Captions) | 67th | 67th | 67th |
| Export tab | 72nd | 72nd | 72nd |
| Render preview | 123rd | 123rd | 123rd |

- PASS: the timeline is now reached right after the player controls (was the 72nd stop from page start; now the 11th from the play button); matches Lane B's numbers (their clip has ~85 chips: 97th / 152nd).
- PASS: layout unchanged at 1280×800 versus my earlier measurement (video 356,144 169×300; timeline 27,579 1226×142; scrollHeight 800 = innerHeight; no horizontal overflow); 390 and 1280×700 keep the scrolling layout, no horizontal overflow (scrollWidth = innerWidth).
- **Remaining Low/Medium (keyboard):** the word chips of the timeline are one Tab stop each, so the inspector now comes after ALL of them (67th stop with 57 words, 97th with 85) and Render preview after the inspector (123rd / 152nd). The cost moved from "reach the timeline" to "leave the timeline". Standard fix without a skip link: make the word chips one roving-tabindex group (one Tab stop, ←/→ or Tab inside moves between words, Enter/Space toggles), or take them out of the Tab order since the timeline already has keys. Owner already said no skip link; this needs no visible UI.
- Note: at 1280×700 the video is 188×334 here versus 254×452 when I measured 44e7847; the 1280×800 rects are identical to before, so this is from the earlier commits (434f6bc controls row / e82389e), not 6a6e0fa. Worth a look together with the small-video decision.

## Not verified
Screen-reader reading order; the new editor.spec DOM-order test (Lane B: 268 passed).

Merge: OK
