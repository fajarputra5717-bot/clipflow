# 146 · P2.5 S2: "Approve & schedule" → planned clip_posts at suggested WIB times · main.py, index.html

- **Why:** P2.5 spec S2 (docs/tasks/P3-campaign-track.md); owner go 2026-10-07 after gate-P2 PASS (qa 3c22a4f).
- **UI:** the clip editor's action row gets "Approve & schedule" (or "Schedule" once the clip is approved/rendered)
  next to Approve, hidden while rules block. It opens `#scheduleSheet` (the shared sheet system): one row per
  platform of the clip (campaign platforms, else the Analyze platform) with a checkbox, account picker, "Post at
  (WIB)" date-time and the account's next 3 suggested slots as chips; amber "Will be recorded as not eligible: …"
  notes come live from a dry run; a platform without an active account links to Settings; posted platforms are
  read-only. Times are edited/shown in WIB (fixed +7) and sent as UTC ISO.
- **API:** `GET /api/jobs/{id}/candidates/{cid}/schedule-plan` → `{approved, status, campaign_name, blocking[],
  platforms[{platform, platform_name, times, post, accounts[{id, handle, suggestions[]}]}]}`; suggestions =
  `schedule.next_slots(POSTING_TIMES, platform, now, taken, rules)` with taken = that account's planned/posted
  minutes. `POST …/schedule {posts[{platform, account_id, scheduled_for}], approve=true, dry_run=false}`:
  Approve gate (409, same text), future time, own active account on that platform, not already posted (409);
  pre-post checks at the planned time via `_eligibility_for` → `eligible` / `ineligible_reason`; queues the final
  render via `_queue_final_render()` (shared with Approve, same version entry) when not approved yet; updates the
  platform's planned post or inserts a new one (a dropped post stays as history). One transaction.
- **Re-plan:** `PATCH /api/posts/{id}` on a planned post with `scheduled_for`/`account_id` re-runs the checks.
- **Publish (144 cards):** a planned chip reads "Planned Thu 8 Oct 19:00"; its panel shows the plan and "Mark
  posted" PATCHes the planned row to posted (a second POST would hit the one-post-per-account rule).
- **Lane C Low (145):** Posting times ✕ now has a 44 px hit area.

**Verified:** UI suite 99 passed (new `schedule.spec.js`: WIB slots, account switch follows suggestions, edited
time, live warning, save body, toggles, blocked clip, phone width; screenshots `schedule-sheet-{desktop,mobile}`);
unit tests OK. Prod (read-only, in-process): plan for an admin IME clip built, `clip_posts` unchanged.
Staging write checks (lane-a users: save, re-plan PATCH, cross-user 404, past time 400, posted 409) after lane-b
merges main.
