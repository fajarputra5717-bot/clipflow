# P4 task 6 — Review page = flow-preview step 4 (+ Lane C carry-over) (lane B)

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
