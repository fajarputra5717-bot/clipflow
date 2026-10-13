# hardening c6bcda4 (202–208) on staging :8080 — re-check of the deep-audit items

Scope: the branch is frontend-only vs a26b041 (diff in backend/worker/shared = main commits 199/200 only), so the cross-user sweep of a26b041 still applies. Staging healthy, sessions kept.

| Item | Result |
|---|---|
| 202 (M2) closed `#jobOverlay` | PASS: `visibility:hidden` + `inert`; 40 Tab stops never reach `#jobOverlayClose` (was reachable after 9) |
| 203/207 (M3) phone fields + sliders ≥ 44 | PASS at 390: the box scan lists only 3 controls < 44 px (`.ai-switch` 51×31, `.ed-switch` 42×26, `.ed-sw-sm` 26×26); Settings inputs and the editor range sliders are gone from the list. `.ai-switch` hit area measured 53×45 via elementFromPoint. The editor switches' ::before hit areas were NOT confirmed (my elementFromPoint probe was inconclusive, sticky bar overlap); taking Lane A's measurement. 768: 71 small controls (36 px stepper nodes, appbar icons, account button) as before, a tablet-size Low |
| 204 (M5) | PASS: with a mocked 500 Publish / Schedule / Track show "Couldn't load …", a 44 px Retry button, the detail text; Retry recovers after the mock is lifted (3/3) |
| 205 (owner bug, dark theme) | PARTIAL: Analyze, Schedule List/Week, Publish filter: pressed = accent rgb(0,102,204) + white, 5.57:1, unpressed unchanged (PASS). **Review filter (`.rv-seg`, "To review / Approved / All") is not accent**: pressed = rgb(28,28,30) thumb on a slightly lighter track (about 1.2:1), readable only by the thumb shape; unlike the other filters. Also the Analyze "Gameplay + face…" tile pressed uses a translucent accent tint (rgba(10,132,255,.17)). Not checked: the Pick filter |
| 206 (M4) CLS | PASS (small miss): with a 300 ms mocked delay on every /api call, first paint CLS 0.026 (390), 0.022 (768), 0.035 (1280) (claim 0.000; was 0.108/0.095/0.039); Import → Review 0 at 390/768/1280 (was 0.084). Well under 0.1 |
| 208 (island +N) | PASS (mocked activity, not a live render): 2 tasks → island click, touch tap and keyboard Tab+Enter all open the list ("2 jobs running", both clips with % and Open ›), overlay visible, not inert; 1 task → opens that clip (`#review/<job>/…`). Live update of the list and a real import + render pair not tested |

## Findings
- Low: 205 incomplete for `.rv-seg` in dark (above). Owner A.
- Low: first-paint CLS 0.02–0.04 remains (claim 0.000). Owner A.

## Not verified
Editor switch ::before hit areas on a real touch device; light theme contrast numbers (Lane A's 4.7); the Pick filter; 208 with real running jobs; M6, L10, L11 (not delivered yet).

Merge: OK for 202, 203/207, 204, 206, 208; 205: OK to merge, with the `.rv-seg` dark pressed state still to fix (Low).
