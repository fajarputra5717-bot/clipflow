# lane-b 3d85c4d · real staging renders + Export actions · 2026-10-09 (Lane C)
Staging only (:8001), user lane-c-a (password reset on staging with owner approval; prod untouched), job b0a4ed97 clip 0a5548a8 (Indonesian, IME), queue idle, one render at a time.
Edits: cuts (pause 8.42-10.26 + filler 23.66-24.02), zoom x3 (60), progress bar, compression. Preview 32 s, final 70 s, both 33.8 s (36.0 - 2.2 s cuts), final 1080x1920.
OK: zoom punch-in, progress bar fills (≈15% → ≈93%), karaoke highlight in sync right after the pause cut (MIRA APA? at out 8.7-8.9 s), watermark + handles present; final LUFS -14.8 (ebur128 I -14.8) TP -1.2; preview -15.4 / -1.1.
Export: generate-description 200 in 5.7 s (Indonesian, campaign hashtags in order); versions 2 ("Applied changes", "Final render requested"); restore v1 200 → description back, preview re-queued, edit_spec kept; v99 404; Approve with hashtags broken → 409 "Fix 1 rule to approve: Hashtags missing or out of order" (clip fixed afterwards); Submagic start → status failed "SUBMAGIC_API_KEY is not configured" (staging has no key), export/use-as-final 409 with clear text.
Findings:
1. Medium (pre-existing, worker make_ass/create_preview, not lane-b): the 540 px preview keeps Outline 9, Shadow 1 and L/R margins 40 while Fontsize and MarginV are halved (ass: PlayRes 540, Fontsize 21, Outline 9; final PlayRes 1080, 42, 9). Preview captions look ~2x bolder / blob-like vs final, so the preview is not WYSIWYG. Scale outline/shadow/margins with canvas_width/1080.
2. Low · loudness lands -14.8 / -15.4 LUFS with compression on (target ~-14); TP OK.
3. Low · filler suggestions include a 10 ms "gitu?" (20.94-20.95, Whisper word timing); PUT cuts silently drops it (removed list shows 2 of 3 ranges). "gitu" is a debatable filler.
4. Low · source_watch.py Mediums from lane-b-3d12912-partial.md stand; the module is imported nowhere yet (no runtime effect), and should adopt shared/ytdlp (167) before it is wired in.
Layout (3d85c4d screenshots): Review 2-col cards with ⋯ menu, disabled Approve + "Fix 1 rule" text, Week closed pill: OK. Mobile editor Render preview 723-767 px vs tab bar from 783: no overlap, hit-test OK, no horizontal scroll. Playwright on staging 187/0.
Not verified: real Submagic render (no key), Thumbnail tab real AI generation, Watermark tab size/opacity re-render, editor UI clicks against the real backend (UI only under the mocked harness).
Merge: OK (editor 5/5b/7a-7e + compact layout + source_watch as an unused module). Open for Lane A: finding 1.
