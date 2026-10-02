# ClipFlow roadmap (decided 2026-10-02)

Target: the full platform from `frontend/html/flow-preview.html`:
Campaign → Auto-import → Analyze → Review → Editor → Schedule → Publish → Track.

**Gate.** A phase starts only after Lane C (QA) signs off the previous one, in `docs/qa/`. Any open **High**
bug blocks the next phase. Each phase ships as one commit per item, with a `docs/changes/` entry, verified on
the running stack.

**Money.** Amounts are IDR first (Rp, `.` thousands). Every payout or claim amount comes from Lane B's
`shared/payouts.py`; nothing hand-rolls payout math in main.py, worker.py or index.html.
Rules files are the input (e.g. Fandra Octo: Rp 12.000 per FULL 3.000-view block, floor, up to 500.000
views → max Rp 1.992.000).

| Phase | Scope | Depends on |
|---|---|---|
| **P0** Stabilise (current queue) | Loudness: Submagic "use as final" path, failure → keep the final + UI warning, ~2× disk reserve, single-pass on previews · unresolvable campaign watermark → failing chip + log, no silent fallback · hashtags at the END, exact order (rules wording "order", not "prefix") · min analysis window 10 min · cleanup: watermark height min 16 %, `WHISPER_LANGUAGE` labelled "Fallback language", version badge bump | n/a |
| **P1** Editor redesign | Per-clip caption presets (`edit_spec`) + "Apply to all clips in this job" · rule chips + "Fix N rules to approve" gate (platform limits from Lane B's `docs/research/publishing-apis.md`, e.g. FB Reels 3–90 s) · existing score shown as "AI estimate" · AI keyword highlight (utility model, stoplists, click to toggle, baked into ASS). Tabs already shipped (082). | P0 |
| **P2** Manual publish (v2a) | accounts · `clip_posts` · Ready to post · pre-post checks · claim advice · Telegram send + 09:00 WIB digest (6 parts, as agreed) | P1 |
| **P3** Campaigns + intake + Track | Campaign screen: brief → rules via Lane B's `brief_parser`, Lane A confirms before saving · auto-import via Lane B's `source_watch` · Track dashboard (views, claims, Rp from `shared/payouts.py`) | P2 |
| **P4** Timeline + effects | Trim timeline + click-to-seek, silence/filler removal (opt-in, Audio tab), zoom punch-ins, hook title, progress bar, transitions + CC0 SFX, using Lane B's `shared/retention.py` | P3 |
| **P5** Auto-post + view pulling | IG/FB Reels auto-post and view pulling into `clip_posts` (official APIs per the research doc) | P4 |

Lane B modules not on main yet: `shared/payouts.py`, `brief_parser`, `source_watch` (P3), plus newer
`lane-b` commits (silence trim off by default, research doc). Each is merged when its phase starts.
