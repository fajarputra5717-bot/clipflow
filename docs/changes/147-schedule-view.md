# 147 · P2.5 S3: Schedule view (stepper step 6 live): planned posts by WIB day, overdue on top, week calendar · main.py, index.html

- **Why:** P2.5 spec S3 (docs/tasks/P3-campaign-track.md).
- **API:** `GET /api/schedule?from&to` (ISO; default = this WIB week Mon 00:00 → +7 d; ≤ 6 weeks else 400): the
  caller's own `planned` posts with `scheduled_for` in range (user_id-scoped; no id in the path), grouped by WIB
  day (`days[{date, posts}]`, every day present), plus `overdue[]` = planned with a time already passed (shown once,
  at the top). Rows = the post + `title`, `has_thumbnail`, `platform_name`, `campaign_name`, `overdue`,
  `render{state ready|rendering|not_approved|failed|missing, label, percent}`; also `posting_times` for free slots.
- **UI:** `#scheduleSection` between Review and Publish (`TAB_SECTIONS` order = stepper order); title "Schedule".
  Week nav ‹ This week ›; List (default; phones) / Week (≥ 1000 px: 7 day columns, a post block opens its list row).
  Row: thumb, title, platform/@account/campaign, WIB time, chips (Overdue red; render state, red when not ready
  < 1 h before or overdue; Not eligible amber with reason), actions Reschedule (the 146 sheet), Send to phone
  (141, that platform's caption; final must be ready), Mark posted (link → PATCH planned → posted), Drop
  (two-step → dropped). Empty future days list the free suggested times. No progress UI outside the island.
- Shell spec: Schedule is no longer a disabled "Coming in P2" step.

**Verified:** UI suite 105 passed (new `schedule-view.spec.js`; screenshots `schedule-week-1280`,
`schedule-list-{1280,390}`); prod read-only: both users get 7 WIB days from Mon 5 Oct, 0 planned; > 6 weeks → 400.
Staging write checks (with S2) after lane-b merges main.
