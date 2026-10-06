# Gate P2 (manual publish v2a): PASS, 2026-10-07

Staging = lane-b 53f34b9 (= main 234f4a0, 144 + editor). Members lane-c-a / lane-c-b. Open Highs: none.

| Area | Result | Evidence |
|---|---|---|
| Posting accounts CRUD, dup 409, pause-not-delete | PASS | lane-c 23/23 on 144 (also Lane A 35/35, QA 22/22 pre-144) |
| clip_posts planned→posted→claimed→paid, paid→planned 409, dup link 409 | PASS | same run |
| Pre-post: cap (3rd TikTok post "Cap reached … 2 of 2"), window (30 Oct "Outside … W1–W4") | PASS | clip_posts.ineligible_reason live |
| Pre-post: length | PASS (code read: main.py `_length_warning`; Lane A specs) | not hit live (clips 29–31 s) |
| Claim advice + views + claimed/paid in IDR | PASS | live panel "Claimed at 41.000 views · expected Rp 200.000" |
| Publish step 7 (144 cards + chips) at 1280/390, git-served + live | PASS | publish.spec 16/16; live no h-scroll, bottom sheet on 390; one card per clip = owner decision vs mock rows |
| Cross-user 404 (accounts, posts, publish-queue, review filters) | PASS | 23/23 + 649ae25/042d0e9 reviews |
| Telegram send-to-phone + 09:00 WIB digest | PASS (code review; owner tests real sends on prod) | Lows: member can set any chat id; 144 caption label |
| Fresh import ime-roleplay (lane-c-a, b0a4ed97) | PASS | layout none, 1080x1920, -14.1 LUFS/-1.1 dBTP, cuts check |
| Fresh import fandra-octo (lane-c-b, f8db9018) | PASS | split facecam, karaoke at seam, Motion Klip watermark ≈27 % (≥16 %), 29.1 s, -14.0 LUFS/-1.2 dBTP, hashtags exact order at end; frames/p2-fandra-lane-c-b.jpg |
| P1 carry-ins: IME default No facecam, one score per card, keyword picker | PASS | main.py:1253 default_layout; 119 |
| Production after 144 deploy | PASS | 5/5 riftstorm-* running, 0 restarts |

Open Lows (not blocking): 234f4a0 #1 Telegram multi-platform caption label; member chooses any Telegram chat id.
