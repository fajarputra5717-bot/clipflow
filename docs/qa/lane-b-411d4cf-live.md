# lane-b 5a58a03..411d4cf (Review / Editor / Sound effects polish) — LIVE checks on staging (lane-b 411d4cf)

Completes docs/qa/lane-b-5a58a03-237edaf-partial.md. Tested as lane-c-a (own data), fresh import for the keyword parts; all test jobs/sounds deleted afterwards.

## Review
- **Finished labels (5a58a03, e052be1, 411d4cf):** against DB rows: completed clip, no post → "Approved · Not scheduled yet"; completed clip with tiktok posted + youtube posted + instagram claimed + facebook planned → "Posted on 3 platforms · next Wed 7 Oct 19:00"; clips still in review show none. Platform names: Facebook, Threads, X, TikTok, Instagram, YouTube all named, and every `posts.PLATFORM_HOSTS` key has a name.
- **Issues (1d31008)** from the real backend `rule_checks`: "No SARA …: “Ilmu hitam” · References to 'black magic' …", 3 issues → two shown + "+1 more (hover the chip)", each 2 lines with ellipsis; no overflow at 1280×900 and 390×844, light and dark. Clips that pass show one "✓ All rules pass" chip.
- **Grouping (2e4cbb5):** across jobs the clips sit under one source heading ("lane-c fresh import 2026-10-13 · Oct 13 · 4 clips") with no title repeated on each card; approved clips show a green "Approved · …" pill instead of a disabled Approve.
- Low: a planned post in the PAST next to posted ones reads "next Wed 7 Oct 19:00" a week later (the single-planned case says "(overdue)", this one doesn't). Low: the full text of a truncated reason is only in the chip's hover title (no touch way to read it).

## Editor
- **Tabs (657819d):** 6 tabs at 360/390/768/1280/1440, none truncated (the row scrolls at 360), 44 px tall on phone.
- **Phone scroll-margin:** at 390 every `.ed-group` in all five tabs (Captions 5, Effects 5, Audio 3, Watermark 1, Export 5) scrolled into view lands at 415–416 px, just under the sticky player (bottom 408): none covered. Focusing a control (`focus()`/Tab) also lands under the player (409).
- **Keywords (10bfa9d):** fresh real import: editor state carries 366 stopwords; the worker's auto-pick for 2 clips = {ngebunuh, serem, dikejar, serius, breakin} and {hantu, merah, takut, serem, locket}: none in the stoplist, all content words (filtered frequent words: gua, dia, udah, anjir, cuy, ya, tuh, ah…). Chips: highlighted first, then the rest; tapping a chip leaves the order unchanged (highlight count +1), at 1280 and 390.

## Sound effects (237edaf)
Uploads show "1.5 s · Your upload · your own rights" (licence on every sound); "Use for …" select 176/216/186 px wide at 1440/390/360, never truncated; a 50-character name wraps; no overflow at 1440, 390 and 360; light and dark.

## Also this run
Fresh e2e (tests/qa/e2e) 10/10 PASS on this build (docs/qa/e2e-run-2026-10-14-b.md): analysis took 16.2 min for the 4 m 44 s video (transcription 889 s; the earlier runs took 570–611 s: staging was shared with Lane A's Groq tests), preview 12 s, final 32 s at −13.9 LUFS / −1.7 dBTP.

## Not verified
Posted/planned labels on a real single-platform Facebook/Threads/X post (unit-checked: all names OK); the issues list for a campaign other than ime-roleplay; keyword ranking beyond highlighted-first (my "MIK" word, 11 uses, ranks below "TURUN" (5): I could not tell if that is the "repeated/longer" rule).

Merge: OK for 5a58a03..411d4cf.
