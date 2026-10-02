# P1 gate checklist (draft) · Editor redesign

Source: docs/roadmap.md P1 row. Run when Lane A reports P1 complete. Any open High = BLOCKED.

## Required (from P1 on)
- [ ] Fresh-import e2e per active campaign (ime-roleplay, fandra-octo), sequential, idle queue: first preview + final
      frames, karaoke, layout, watermark, −14 LUFS / TP ≤ −1 dBTP, hashtags exact order at caption end, render chips
- [ ] Playwright suite (tests/ui, Lane B) + QA specs (qa-capsule; add P1 cases)
- [ ] UI vs spec: screenshots at 1280 and 390 px of each BUILT step next to `frontend/html/flow-preview.html`
      (steps via `[data-step="<id>"]`: campaign, import, analyze, review, editor, schedule, publish, track).
      P1 → **review** (rule chips, "Fix N rules to approve", score as "AI estimate") and **editor** (tabs, per-clip
      caption presets + "Apply to all clips in this job", keyword highlight). List differences: layout,
      components, wording. Mock data / USD vs real data / IDR = expected.

## P1 scope items (roadmap)
- [ ] Per-clip caption presets (`edit_spec`) + "Apply to all clips in this job"
- [ ] Rule chips + "Fix N rules to approve" gate; platform limits from docs/research/publishing-apis.md (e.g. FB Reels 3–90 s)
- [ ] Existing score shown as "AI estimate"
- [ ] AI keyword highlight: utility model, id/en stoplists, click to toggle, baked into the ASS (check final frames)
- [ ] Island rule: every new progress state (keyword AI call etc.) in the island / row capsules only
