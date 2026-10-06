# Gate P1.5 · Multi-user accounts · **PASS** · 2026-10-06
Reviewer: Lane C. Staging = lane-b b0d73b9 (= main 24ce3eb, P1.5 parts 1–5 + 127). QA members qa_a / qa_b (created via
the admin API on staging; passwords never printed). No open High.

## Cross-user isolation (HIGH class): all PASS
- `qa-multiuser.spec.js` on staging (guarded to :8001/:8080): **9/9 passed, 0 skipped**: B → 404 on A's job, candidates,
  candidate, versions, files (preview/thumbnail/render/watermark, with or without B's media token); B's lists and
  /api/activity never show A's rows; B's PATCH/approve/regenerate/cancel/delete on A's clip → 404, A's data unchanged;
  member PUT of a global key → 403 (value re-sent unchanged); unauthenticated → 401.
- Lane-b editor (d19b286): A GET/PUT own clip 200/200; **B on A's clip 404/404**.
- Tokens (124): B's cf_ token: own list 200, A's job **404**, mint via token 403, admin route 403, revoke → 401; DB stores
  sha256 only.
- P2 objects on the same guard: accounts + posts cross-user 404 (p2-writechecks-staging-2026-10-06.md, 22/22).
- Lane A's staging write checks (cited): 56/56 P1.5 + 35/35 P2.

## Auth mechanics
argon2 hashes, hashed DB sessions (HttpOnly + SameSite=Lax, Secure on HTTPS), Origin belt for cookie writes, DB-backed
login rate limit, no signup, admin-only user management, forced change after temporary passwords (member API 403 until
changed → 200), last-admin guard (Lane A), per-user hashed tokens; shared key removed (127, owner decision).

## Per-user settings + worker
B set its own DEFAULT_SUBTITLE_STYLE = neon; A still saw outline. B's fresh Fandra import (job fa654662) was created
with style **neon** and the final renders neon captions (`frames/gate-P1.5/B-fandra-final.jpg`) → worker uses the job
owner's settings ✓. Global keys hidden from members, 403 on write ✓.

## Member e2e (fresh imports on staging)
| member | campaign | layout | final | I / TP | hashtags (order, end) |
|---|---|---|---|---|---|
| qa_a | ime-roleplay | none (campaign default) | 1080×1920, karaoke ✓ | −14.3 / −1.3 ✓ | ✓ (at analysis) |
| qa_b | fandra-octo | panel (cam) | 1080×1920, neon ✓ | −14.1 / −1.0 ✓ | ✓ |

## UI
Playwright at 93782a8 (git-served): 56/56; lane-b suite on staging: 88/88. Login page matches the mock's style (card,
logo, blue primary). Island + stepper unchanged (island/capsule specs pass).

## Carried over (none blocks)
1. Low · username lockout DoS (5 bad passwords lock a username 15 min).
2. Low · staging restores production users + sessions; cookies are host-scoped → a production login cookie works on :8080.
3. Process · staging worker restarts killed QA's job (3 attempts → failed) and cross-lane test-data edits; owner rule now
   in force (lane-prefixed data only). Lane A overwrote the descriptions of qa_a's job 2ee13f97 after QA's evidence was
   captured (final + description recorded before 14:02); QA had reassigned restored admin job 1522410e (owner to decide).
## Not verified
Production with real members (by design, staging only); legacy-row migration counts (code-read `assign_legacy_rows` +
Lane A); Telegram (P2 part 6, not built).
