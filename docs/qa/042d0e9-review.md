# 042d0e9 (lane-b) fix(review): QA 649ae25 Lows — QA 2026-10-07

1. Spec: review.spec.js runs with reducedMotion "reduce". Lane B reports 15/15 on mobile with --repeat-each=3; staging suite 123 passed.
2. PUT /api/review/filter on staging 53f34b9 as lane-c-b: lane-c-a's job id is stored as "all", an unknown campaign as "all",
   and B's own job id is kept. Fixed.
3. fix()/approve() call setBusy(false) in a finally when btn.isConnected. Fixed (code read).
No new bugs. Merge: OK.
