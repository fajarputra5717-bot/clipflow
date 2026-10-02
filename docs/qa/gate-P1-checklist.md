# P1 gate checklist (draft) · Editor redesign

Source: docs/roadmap.md P1 row. Run when Lane A reports P1 complete. Any open High = BLOCKED.

## Carry-in to fix before the P1 gate
- [ ] 101 regression: static HUD passes as a facecam → junk panel on all clips of a no-cam source (1dfb5ad #0)

## Required (from P1 on)
- [ ] Fresh-import e2e per active campaign (ime-roleplay, fandra-octo), sequential, idle queue: first preview + final
      frames, karaoke, layout, watermark, −14 LUFS / TP ≤ −1 dBTP, hashtags exact order at caption end, render chips
- [ ] Playwright suite (tests/ui, Lane B) + QA specs (qa-capsule; add P1 cases)
- [ ] UI vs spec: screenshots at 1280 and 390 px of each BUILT step next to `frontend/html/flow-preview.html`
      (steps via `[data-step="<id>"]`: campaign, import, analyze, review, editor, schedule, publish, track).
      P1 → **review** (rule chips, "Fix N rules to approve", score as "AI estimate") and **editor** (tabs, per-clip
      caption presets + "Apply to all clips in this job", keyword highlight). List differences: layout,
      components, wording. Mock data / USD vs real data / IDR = expected.

## P1 task 0 · UI shell (owner 2026-10-02)
- [ ] 8-step stepper is the top-level navigation (Campaign · Auto-import · Analyze · Review · Editor · Schedule ·
      Publish · Track), same order/labels as the mock
- [ ] Unbuilt steps disabled with "Coming in P2" / "Coming in P3" (per roadmap phase), not clickable, accessible
      (aria-disabled + tooltip/label)
- [ ] Mockup visual system app-wide (tokens, type, cards, buttons, chips as in flow-preview.html)
- [ ] Job status island unchanged (behaviour + look; Playwright island spec + qa-capsule still pass)
- [ ] Settings still reachable (and Watermarks)
- [ ] Money in IDR (Rp, "." thousands) everywhere it appears; no USD
- [ ] Shell itself compared to the mock at 1280 + 390 px (stepper, header, nav, sheet entry points)
- [ ] Per roadmap mapping (fa27f18): Campaign, Auto-import, Track disabled "Coming in P3"; Schedule, Publish disabled
      "Coming in P2"; Analyze = today's Import view; Review = today's "Publish" view renamed; Editor disabled until a
      clip is picked, then opens that clip's editor; Settings via sidebar AND toolbar gear; no money on any screen
      before P2; disabled steps show no mock content
- Screenshot pairs to take (app step ↔ mock `[data-step]`): analyze ↔ analyze, review ↔ review, editor ↔ editor,
  each disabled step ↔ its mock step (to confirm only the placeholder is shown), shell at rest ↔ mock at rest

## P1 scope items (roadmap)
- [ ] Per-clip caption presets (`edit_spec`) + "Apply to all clips in this job"
- [ ] Rule chips + "Fix N rules to approve" gate; platform limits from docs/research/publishing-apis.md (e.g. FB Reels 3–90 s)
- [ ] Existing score shown as "AI estimate"
- [ ] AI keyword highlight: utility model, id/en stoplists, click to toggle, baked into the ASS (check final frames)
- [ ] Island rule: every new progress state (keyword AI call etc.) in the island / row capsules only
