# Gate P0 · Stabilise · **PASS** (no open High) · 2026-10-02 15:25 WIB

Reviewer: Lane C. Main @ e7ccdc3 ("P0 built, awaiting Lane C sign-off", 083–098), deployed backend + worker
confirmed. Checklist: docs/roadmap.md P0 row + owner fold-ins (gate-P0-checklist.md). Playwright not required
for P0 (Lane B's harness was run anyway on 556cca7: 22 pass / 4 skipped / 0 fail).

**Verdict: PASS.** No High bug is open. P1 may start. Carried over, ranked below: 2 Medium + 5 Low, two of which
are unfinished P0 checklist items (#1, #5). Fix #1 before campaign volume grows.

## Fresh-import e2e (one job per active campaign, sequential, idle queue)
| job | campaign | source | layout decided | clips |
|---|---|---|---|---|
| 6d4cc439 | ime-roleplay | GTA RP bRJnLhJruyc (no cam) | `full` (1/2 detected, tie without agreement) | 2882705c, 185c6aeb |
| b51f7a30 | fandra-octo | FC26 Zgu4B5C7e-Y (facecam) | `panel` (2/2) | 3bee698c, 8c7795ef |

| clip | 1080×1920 | final I / TP | preview I / TP | karaoke (preview + final) | words | hashtags (order, end) | watermark | warnings |
|---|---|---|---|---|---|---|---|---|
| 2882705c | ✓ | −14.0 / −1.3 ✓ | −14.1 / −0.8 | ✓ | 20/20 | ✓ | 8f7158d7 ✓ | none |
| 185c6aeb | ✓ | −14.3 / −1.1 ✓ | −14.3 / −1.0 | ✓ (final) | 12/12 | ✓ | ✓ | none |
| 3bee698c | ✓ | −14.0 / −1.1 ✓ | −14.1 / **+0.1** | ✓ | 10/10 | ✓ | ✓ | none |
| 8c7795ef | ✓ | −14.1 / −1.2 ✓ | −14.0 / −0.8 | ✓ (final) | 21/21 | ✓ | ✓ | none |
Titles: Indonesian, hook-first, ≤ 90 chars (all 4). Frames: `frames/gate-P0/final-*.jpg` (0/25/50 %/end),
`frames/gate-P0/karaoke-*-preview-vs-final.jpg`.

## Checklist
| P0 item | result |
|---|---|
| Loudness on finals (−14 / ≤ −1 dBTP) | ✓ 4/4 this gate |
| Loudness on Submagic "use as final" | code-read only (export is billable) |
| Loudnorm failure → keep final + chip | code-read only (091) |
| ~2× disk reserve | ✓ code (091) |
| Previews loudness | ✓ ≈ −14; Low: TP up to +0.1 dBTP (#6) |
| Unresolvable campaign watermark → chip, no silent fallback | **partial**: worker ✓ (092); job creation still falls back silently (#1) |
| Hashtags exact order at end; rules wording | ✓ live on 4 descriptions + 093 |
| Min analysis window 10 min | ✓ (094, tested) |
| Watermark height 16–85 %, "Fallback language", badge v2.1117 | ✓ (098) |
| Per-job layout | ✓ GTA full / Fandra panel (095); Medium risk on 2-clip ties (#2) |
| Full-frame caption height | ✓ 78 % (096); Low: sits on in-game HUD on this source (#4) |
| Island-style row capsules | ✓ (097) |
| 090 fold-ins: activity errors, running allowlist, Submagic indeterminate | **not done** (#5) |

## Carried-over blockers-for-later (none blocks P1)
1. **Medium · campaign watermark falls back silently at job creation** (`campaign_watermark_snapshot()` stores
   NULL → worker uses the active mark, no chip). e28421e-review #1.
2. **Medium · loudness re-measure is never acted on**: earlier finals came out −15.8 LUFS and +2.3 dBTP
   (2 samples) with no chip/second pass (6c1d231 #1, recheck-092). Not reproduced on the 4 gate finals.
3. **Medium · 2-clip ties drop a real facecam** (095 rule): a facecam stream with one missed clip → both
   full-frame. Not hit in this gate (Fandra 2/2). 981a001-review #1.
4. Low · full-frame captions at 78 % can sit on in-game HUD / under the right icon column (096).
5. Low · 090 fold-ins not done: `/api/activity` errors swallowed (index.html:2641), `JOB_RESTING` deny-list
   (main.py:890), Submagic fake 50 %.
6. Low · preview true peak up to +0.1 dBTP (96k, no re-measure).
7. Low · job-creation clamp for WATERMARK_POSITION_Y still 5–95 (unreachable via Settings).

Outside P0 scope: lane-b payouts Medium (IME advice after Oct 28), before P2/P3. Manual review items: IME clips
pairing religious exclamations with the burning gag (SARA rule); GTA source shows @valkeyw socials full-frame.

## Not verified
Submagic final loudness, forced loudnorm failure, missing-asset render path (all code-read); Playwright live mode.
