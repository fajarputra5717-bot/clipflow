# lane-b b85de37 (Auto Edit E3: emoji + SFX) + 32d5c37 (E2 Lows) · Lane C · 2026-10-13
Staging = b85de37. Own data only (lane-c-a clip B 5d905d89, 55 s, cut 20-21 s). Unit tests motion / edit_director / retention OK; tests/test_overlays_sfx.py is Lane B's.
E2 Lows (32d5c37) verified: plans no longer start before 0.5 s (first item 3.1 s); with a cut at 20-21 s the new plan proposes a whip at the seam (whip 21.0, source "cut"); on clips A/C the seam is still dropped when a transcript item is within 3 s output seconds (restraint, fine). Flash hint wording not looked at.
E3 live (items: 😂 + ding 11.0, whip + whoosh at the seam 21.0, punch + boom 39.1, freeze + record_scratch 49.6, 💀 + bass_hit 53.7): worker "Emoji: 1 pop(s)" / "SFX: 4 mixed under the speech (whoosh, boom, record_scratch, bass_hit)" / "55.0 s -> 54.6 s + time effects (freeze)"; after restoring the 😂 item: preview 54.61 s, render 46 s (43 s before E3 on the same clip).
- Frames (4: emoji ×2, whip at the cut, punch): 😂 right and 💀 left, between the watermark and the captions, never covering either; whip blur with caption and watermark crisp; nothing off-canvas.
- SFX audible: 0.3 s RMS windows at the effect vs just before: ding +4.6 dB, whoosh +4.6, boom +4.6, bass_hit +11.5 dB (windows include speech). Preview -15.4 LUFS / -1.2 dBTP with Loud & punchy off (owner-accepted undershoot, TP ok); Lane B's final on 2a497ffb: -13.7 / -2.7.
- Licences: worker/assets/LICENSES.md covers watermark.png (Motion Klip), emoji/*.png (Twemoji 15.1.0, CC-BY 4.0, credit text) and the 5 in-house CC0 SFX; tests/qa/check_asset_licenses.py (extended for glob rows, in-house SFX source and CC-BY attribution text) exits 0 on b85de37. No laugh bundled.
No High/Medium. Low:
1. Low · PUT /plan stores unvalidated params: sfx "laugh" and emoji "<script>" returned 200 and were saved (render drops them silently; the editor escapes them, so no XSS). Validate against director.sfx / director.emoji, 400 otherwise.
2. Low (owner/legal) · CC-BY 4.0 emoji are burned into published videos, but the credit lives only in LICENSES.md/docs: decide where the credit travels (post description or an about page).
3. Info · when two items sit in one window (my 😂 then the invalid emoji) the picker overwrote the sound: expected.
Not verified: a FINAL with E3 by me (Lane B's final measured), Sound/emoji pickers visually, ducking quantitatively, emoji position on the 1080 final.
Merge: OK.
