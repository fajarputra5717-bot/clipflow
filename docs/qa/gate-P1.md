# Gate P1 · UI shell + editor redesign · **PASS** (with carry-overs) · 2026-10-03, HEAD 8e51f32 (106–116)

Reviewer: Lane C. Gated commit: main @ 985cacb ("P1 built (106–114)"); 115 (descriptions at analysis) was
deployed during the run and is included. Checklist: gate-P1-checklist.md. Playwright run against a git-served copy
of 985cacb (not the live working tree).

**Final verdict (owner decision 2026-10-03): PASS.** The owner accepted the workaround and re-rated #1 Medium (see
"Owner decision" at the end). Original QA verdict was BLOCKED by one High (#1). Everything P1 built works. If the owner accepts the workaround for #1
(import IME's GTA source with Facecam → "No facecam") and rates it Medium, this gate is a **PASS** with the items
below carried over.

## Blockers
1. **High · junk camera panel on default IME imports of the GTA source (2 of the last 3).** Correction after the
   HEAD re-run: not every import. Since 101: fbda481f junk (tie path), 7e84933b junk (majority 2/2), 1f9224b0 clean
   (0/2 detected → full-frame, `frames/gate-P1/rerun/`). It depends on which moments the AI picks. Earlier text:
   third fresh GTA job in a row with
   the junk bottom panel: job 7e84933b decided `panel` by **majority** ("2/2 clips detected a face") → both finals
   show a zoomed slice of the source's chat overlay / shirt / floor in the bottom 30 %
   (`frames/gate-P1/final-a63edbbb.jpg`, `final-e989b2d0.jpg`). Earlier: fbda481f via 101's tie path (HUD at
   (0.94, 0.67)). So the detector itself returns stable false positives on this game (HUD/overlay/characters);
   neither the majority nor the tie rule can fix that. Raised from Medium because it hits most default imports of the
   active campaign's source and regresses a P0-gated item; the owner may rate it Medium given the workaround. Fix ideas: require a face detector score floor
   + more hits (real cams: 15–37, spread ≤ 0.012), reject boxes whose content doesn't change between samples (HUD),
   or a per-campaign/per-channel layout default (IME source = no facecam).

## Fresh-import e2e (sequential, idle queue)
| clip | campaign | layout | preset / caption_y / keywords | final I / TP | hashtags (order, end) | warnings / chips |
|---|---|---|---|---|---|---|
| a63edbbb | IME | panel ✗ (#1) | **Hormozi** (hormozi+bounce) / **62 %** / green | −14.2 / −1.3 ✓ | ✓ (at analysis, 115) | none; safety [] |
| e989b2d0 | IME | panel ✗ (#1) | job default / auto / AI (yellow) | −14.1 / −1.3 ✓ | ✓ | safety: "Anjik" (no_sara_or_insults) |
| 71f7ff44 | Fandra | panel ✓ (cam) | **Hormozi** / **85 % → stays at the seam** ✓ / green | −14.0 / −1.1 ✓ | ✓ | none |
| b85232f7 | Fandra | panel ✓ | default karaoke | −14.1 / −1.3 ✓ | ✓ | none |
All 1080×1920. Keywords baked in green in the finals ("GILA", "INDAH", "ASTAGHFIRULLAHALADZIM":
`frames/gate-P1/keywords-*.jpg`); Hormozi/bounce preset visible on both preset clips; caption_y 62 moved IME clip 1's
captions up; Fandra 85 clamped to the seam (never into the cam).

## Rule gate (Approve + Submagic)
On QA clip e989b2d0 (completed): description without hashtags → `POST …/approve` **409** "Fix 1 rule to approve:
Hashtags missing or out of order", status stayed `completed`; with `submagic_status=completed` → `POST
…/submagic/use-as-final` **409** with the same rule message, nothing queued; `fix-rule hashtags` → description ends
with the 5 tags in order. All restored. (Positive path: fresh campaign clips now have hashtags from analysis (115), so
Approve 200 is correct.)

## Playwright
Lane B suite on git-served 985cacb + QA specs (capsule, steps-vs-mock): **38 passed, 4 skipped, 0 failed**,
desktop 1280 + mobile 390.

## UI vs flow-preview mock (screens in `frames/gate-P1/ui/`)
Shell (as in ui-shell-vs-mock-2026-10-02 #1–#6): sidebar + page title vs mock's top header; no stepper card header;
built-step subtitles worded differently; mobile has stepper + bottom tab bar; mobile disabled steps show no reason.
Review step: mock = horizontal clip cards (thumbnail left, "Hook 94", title, reason, rule chips with inline fix links,
"Approve & schedule" + "Open editor"), sorted by score, "4 to review"; app = tall cards dominated by a video player,
"AI estimate N" + reason, full-width "Get another hook" / "Try Submagic edit" buttons, a "★ n/10" rating overlay
(2 scores), Approve only inside the drawer. Editor step: mock = its own page (eyebrow, title, Virality chip, chips,
player left, tabs right, 3×2 preset grid, keyword section, sticky "Fix 1 rule… · Render preview · Approve & schedule");
app = the drawer inside a half-width Review card next to the other clip, sticky "Apply changes · Approve". Mobile
editor opens scrolled to the player; bottom tab bar highlights "Review" while the title says "Editor". No money on any
screen ✓ (no USD).

## Carried over (none blocks except #1)
2. **Medium · Editor/Review layout ≠ mock steps 4–5** (drawer in a card vs dedicated editor page; tall player cards vs
   compact clip cards). Owner decides whether this is P1 scope or later.
3. Low · two scores on a card (AI estimate + ★ rating).
4. Low · mobile: disabled steps give no reason; tab bar says Review while in Editor; two navigations.
5. ~~Low · default keyword yellow = karaoke highlight~~ FIXED by 116.
6. Low · AI keyword picker emphasised "ASTAGHFIRULLAHALADZIM" on a SARA-flagged IME clip; consider excluding
   religious exclamations from keyword picks.
7. Low (P1 backlog) · peaky audio ~−15.2 LUFS + chip; light compression before loudnorm.
8. Low · full-frame "No facecam" captions over in-game HUD → now fixable per clip (112) ✓.

## Not verified
Submagic final render end to end (billable); "Final outdated" chip live (code + Lane A); dark theme comparison.

## Re-run at HEAD 8e51f32 (2026-10-03, after 116)
- **116 keyword contrast: FIXED** on a fresh import (green keywords next to yellow karaoke, preview + final;
  8e51f32-review.md). Closes carried-over #5.
- **Playwright** (git-served 8e51f32, Lane B suite + QA capsule + steps-vs-mock): **38 passed, 4 skipped, 0 failed**.
- **Blocker #1 re-tested:** fresh default IME import 1f9224b0 → `full` (0/2), clean. Blocker stays open: 2 of 3 default
  GTA imports since 101 still got the junk panel, and no commit touches face detection.
- Nothing else changed since the first run (only 116 landed), so the e2e, rule-gate and UI-vs-mock results above stand.

**Verdict at HEAD: still BLOCKED by #1 (High).** PASS if the owner accepts the "No facecam" workaround / rates #1 Medium.
New since the first run: Low · corrective loudness pass can leave −0.6 dBTP with the chip (8e51f32 #1).

## Owner decision (2026-10-03) → **PASS**
- #1 re-rated **Medium** (workaround accepted). Lane A makes "No facecam" the IME campaign default and fixes face
  detection first in P2. QA re-checks both at the start of P2 (fresh default IME import → full-frame; facecam
  sources still get the panel).
- Carry-over owners:
  - #2 Review/Editor not matching mock steps 4–5 (editor as its own page) → **Lane B** (P4 editor work).
  - #3 two scores on cards (AI estimate + ★ rating) → **Lane A**.
  - #6 keyword picker emphasises religious exclamations → **Lane A**.
  - Remaining Lows (mobile nav quirks, corrective-pass TP −0.6 dBTP, compression backlog) → Lane A backlog.
