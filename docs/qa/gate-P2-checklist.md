# P2 gate checklist (draft) · Manual publish (v2a)

Source: docs/roadmap.md P2 row (accounts · clip_posts · Ready to post · pre-post checks · claim advice · Telegram send +
09:00 WIB digest). Expand when P2 starts.

## Carry-ins from P1 (owner 2026-10-03), re-check first in P2
- [ ] IME campaign defaults to layout "No facecam" (fresh default IME import → full-frame)
- [ ] Face detection fixed: no-cam GTA source never gets a panel; Fandra (facecam) still does (≥ 3 fresh imports each)
- [ ] Two scores on cards resolved (Lane A)
- [ ] Keyword picker skips religious exclamations (Lane A)

## Standard
- Fresh-import e2e per active campaign, frames + LUFS, rule checks, Playwright (git-served), UI vs mock for each
  newly built step (Schedule / Publish at 1280 + 390), money in IDR from shared/payouts.py.

## Lane A's staging write checks (2026-10-06, staging = lane-b b0d73b9 = main 24ce3eb): 35/35 PASS (cited)
Accounts CRUD + dup 409 + B PATCH 404 · approve-blocking rule → posting 409 · IME cap (3rd post/month eligible=false
"Cap reached … (2 of 2)") · duplicate link 409, http/wrong host 400 · cross-user posts read/patch/delete/create → 404 ·
lifecycle 409/400 · views history + claim_now · claimed Rp 200.000, paid difference "−Rp 10.000" · account with posts
paused not deleted · 137 new-hook distinct ranges. Details: docs/changes/133, 137.
## Left for QA at the P2 gate
- Publish queue rows on a REAL member final (qa_a has one on staging: 82f725e4), download name, caption copy
- UI vs mock: Publish (step 7) + Schedule/Track placeholders + Analyze (step 3, 126) at 1280/390
- Fresh-import e2e per campaign as a member; Telegram (part 6) once built
- P1 carry-ins (face detection ✓ 118, two scores, keyword picker ✓ 119)
