# lane-b: Review / Editor / Sound effects polish (owner 2026-10-14, Phase 2, Lane B items)

1. Review, approved clips: `shared/review_state.finished_label(status, posts, now)` (pure, tested) →
   "Approved · Scheduled Wed 17:00" (WIB; date added beyond a week; "(overdue)"), "Approved · Rendering final",
   "Approved · Not scheduled yet", "Posted on TikTok · next Thu 17:00" / "Posted on 2 platforms". `review_clips` returns
   it as `finished` (posts query adds `scheduled_for`); the card shows it in place of the disabled Approve, without the
   status badge or hint line it repeated.
2. Review rule chips: only failing checks get a chip (`checksHtml()`); when all pass, one "✓ All rules pass" whose
   title lists the passed rules. The "All campaign rules pass." hint line is gone (the chip says it).
3. Review across jobs (`job = all`): clips are grouped by source video (`byJob()`): one heading "title · date · N clips"
   per group instead of the source title on every card. Groups keep the server order (best clip first), clips inside
   keep it too (hook score, earn last). The intro says "Grouped by video, best hook first."
