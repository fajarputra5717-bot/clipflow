# 155 · P4 task 6 — Review page = flow-preview step 4 (+ Lane C carry-over) (lane B)

**Page.** `frontend/html/editor/review.js` (one `<script>` hook in index.html), its own view at `#review` /
`#review/<jobId>`, mounted in the app shell after switching the shell to its Review step (`showTab("queue")`),
so the toolbar title + stepper show Review like the mockup; the editor's "← Review" returns here.
- Job picker on top: compact dropdown (title = custom title or the YouTube title, "YouTube · campaign · date",
  status badge), keyboard Escape, URL follows the selection.
- Header: "Step 4 · Review", job title, "Clips are sorted by hook score. A clip can be scheduled only when every
  campaign rule passes.", "N to review" badge.
- Grid: 2 columns (1 at ≤ 900 px), sorted by hook score (desc, then clip index); works with any clip count.
  Card: thumbnail + duration badge (output length after cuts), "Hook N · AI estimate", title, AI reason with
  the first clause bold, rule chips (`rule_checks`, the ONE source) with one-click fixes beside failing ones,
  Approve (blocking failures disable it; "Approve & schedule" once P2 scheduling lands), Open editor, and
  "Fix N rules to approve." / "All campaign rules pass." / "No campaign rules for this job." under them.
  Cards are keyed and only repainted when their data changes (poll while renders run; progress = island).
- Fixes: length → "Trim to N s" → `PUT …/editor/fix-length {target}` (ends the trim where the OUTPUT reaches
  N s, existing cuts kept); hashtags → "Add tags" and safety → "Dismiss" → Lane A's `fix-rule`; missing
  campaign watermark → "Fix watermark" → `regenerate-preview`.

**shared/rule_checks.py.** Length = the posted length (clip minus `edit_spec.cuts`); too long → `fix: "trim"`
+ `fix_target` = strictest failing platform limit − 2 s ("Trim to 88 s" for Facebook's 90 s); too short has no
fix. Missing campaign watermark → `fix: "rerender"`.

**Verified on staging** (admin-owned IME job 31dc06f4, made 4 clips with staging-only test data): sorted
94/88/71/63, "4 to review", 2 columns at 1280 / 1 at 390, no overflow; Trim to 88 s → badge 1:28 and chip
green; Add tags → chip green; hints + Approve gate update; picker lists 22 jobs. Screenshots vs the mockup's
step 4 at 1280 and 390: same structure and order of elements; differences = the job picker (asked for) and the
"AI estimate" label. Found on the way: every cookie-session write from the :8080 UI was 403 (Origin vs
port-less Host) → staging-only fix in its own commit. Tests: `tests/test_rule_checks_editor.py` (5),
`tests/ui/specs/review.spec.js` (4 × 2 viewports); UI suite on staging 111 passed; unit 102 OK.

**For Lane A at merge:** point the stepper's Review step at `#review` (and remove the old queue detail with the
drawer).

## Filters (2026-10-07) — before the production merge; mock step-4 card design kept

- Filter bar: Campaign (All campaigns / each / No campaign) · Job (All jobs / the campaign's jobs, "title · date") ·
  Status (To review [default] / Approved / All). Remembered per user: `GET/PUT /api/review/filter` →
  `user_settings` key `REVIEW_FILTER` (not a settings-UI key). `#review/<jobId>` presets the job (editor "← Review").
- `GET /api/review/clips?campaign=&job=&status=` (owner-scoped by `jobs.user_id`, jobs in review/completed/
  partial_failure): one list across jobs with `rule_checks`, `job_title`/`job_date` (source label), `earn`; earnable
  clips first by hook score, then the ones that can no longer earn. Header: job (title) or campaign (name +
  status "IME Roleplay · Week 2 · 6 days left" / "Open until the budget runs out" / "Ended") + "N to review".
- `shared/review_state.py`: `campaign_status()` and `earn_state()` phrase payouts.py's windows/periods:
  "Campaign ended" (period over) or "Week closed" (FixedThreshold: every post went up in a closed week, or unposted
  and today is outside every week window). Badge on the card, card dimmed, sorted last.
- Empty state per filter ("No IME Roleplay clips to review. Import a video on Analyze…").
- Verified on staging (1280/390): IME all jobs = 7 to review, sorted 94/92/88/63/…, a staging-only test post
  (`clip_posts.id = lane-b-test-weekclosed`, posted 30 Sep, admin) shows "Week closed" last; filter kept after reload;
  job filter → job header, no source labels, URL #review/<job>; MotionKlip + Approved → empty state; 2 / 1 columns,
  no overflow. Tests: `tests/test_review_state.py` (4), `tests/ui/specs/review.spec.js` rewritten (5 × 2);
  UI suite on staging 121 passed; unit 116 OK.
