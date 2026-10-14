# lane-b: Review / Editor / Sound effects polish (owner 2026-10-14, Phase 2, Lane B items)

1. Review, approved clips: `shared/review_state.finished_label(status, posts, now)` (pure, tested) →
   "Approved · Scheduled Wed 17:00" (WIB; date added beyond a week; "(overdue)"), "Approved · Rendering final",
   "Approved · Not scheduled yet", "Posted on TikTok · next Thu 17:00" / "Posted on 2 platforms". `review_clips` returns
   it as `finished` (posts query adds `scheduled_for`); the card shows it in place of the disabled Approve, without the
   status badge or hint line it repeated.
