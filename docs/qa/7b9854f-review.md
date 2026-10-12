# lane-b 7b9854f (Auto Edit E4: look) + 5d8cdde (params validation) · Lane C · 2026-10-13
Staging = 7b9854f. Own data: lane-c-a clip C 23855acf (36 s, cut 11-12 s, shake/whip/punch + 😂 pops). Unit tests motion / edit_director / retention / overlays_sfx OK; license checker exits 0.
5d8cdde (my params Low) FIXED: PUT /plan sfx "laugh" 400, emoji "<script>" 400, freeze hold 99 400, slow-mo factor "x" 400; a bundled sfx still 200. Look API: unknown preset 400 "Unknown look 'nope'", non-bool vignette 422, {} = none (200).
E4 live, same plan, four previews (look none / vivid_gaming / warm / moody + vignette + grain), frame at 17.9 s (output):
- Footage graded as described: vivid cooler/more saturated, warm subtle, moody darker with a visible vignette; the 😂 emoji, the caption (yellow "HAH" highlight + white) and the white watermark look identical across looks. Emoji centre colour none (250,194,71) vs vivid (247,198,77), warm (248,197,79), moody (248,199,78): ≤ 8/255 difference (encoding), i.e. not graded.
- LUFS/TP identical in all four previews: -14.2 LUFS / -1.2 dBFS (look doesn't touch audio).
- Render time: none 30 s, every look preset 49 s (+19 s, +63 %) for a 36 s preview.
No High/Medium. Low:
1. Low · a look adds ~63 % to the preview render (30 → 49 s); fine against the 300 s watchdog, but finals with look + effects deserve a timing line in the change doc (not measured by me on a final).
2. Low · "warm" is barely distinguishable from "none" at this strength (frames); consider a stronger tint or say "subtle" in the picker.
Not verified: FINAL with a look by me (Lane B reports 0782e50b final -14.3 / -5.3), the Look picker UI visually, grain/vignette at 1080.
Merge: OK.

## Re-check 2026-10-13 · d6dbddd (both E4 Lows) on staging, same clip C
Staging worker has the YUV looks (lutyuv present). Preview render times: none 31 s, vivid 35 s, warm 31 s, moody + vignette + grain 33 s (before: 30 / 49 / 49 / 49 s) → overhead ≤ 4 s: Low 1 CLOSED. Warm now reads as a visible amber shift in the frame (none vs warm vs moody at 17.9 s): Low 2 CLOSED. Emoji centre colour within 4/255 of "none" in all looks (emoji not graded), caption + watermark intact, LUFS/TP identical (-14.2 / -1.2) in all four. Not verified: finals with a look by me.
