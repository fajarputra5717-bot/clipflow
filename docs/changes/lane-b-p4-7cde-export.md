# P4 task 7c–7e — Watermark + Export tabs, "All edits" removed (lane-b)

- `GET …/editor` adds `watermark {width, opacity, custom}` and `export {burn, description, submagic}`.
- Watermark tab: job size/opacity → `PATCH /api/jobs/{id}/render-options`.
- Export tab: burn toggle (render-options), description + AI generate (candidate PATCH / generate-description), Submagic start/export/use-as-final (polled), version history + restore (two-tap), Approve (server rule gate, 409 text shown).
- Review card: "All edits" button removed (`data-rv-classic`).
Drawer pieces covered: Watermark tab, Export tab (burn, description, Submagic row, versions, approve), Apply/Final render (Render preview + Approve).
