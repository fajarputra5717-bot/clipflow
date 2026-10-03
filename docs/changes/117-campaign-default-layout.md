# 117 · Campaign default facecam layout (rules "default_layout"; IME = no facecam) · docs/campaigns, shared/campaigns.py, main.py, index.html

- Rules files: `default_layout` ∈ auto|left|right|none. IME Roleplay = `none` (GTA RP streams, no facecam);
  Fandra Octo and Motionklip Windah = `auto` (their streams have a facecam).
- `shared/campaigns.default_layout(rules)` (unknown → auto); `/api/campaigns` returns it.
- `POST /api/jobs`: `layout` omitted (API callers) → the campaign's default, else auto.
- Import form: choosing a campaign pre-selects its layout unless you picked one yourself (`layoutTouched`);
  back to "None" resets Auto (if you didn't pick).

**Verified:** `/api/campaigns` → fandra auto, ime none, windah auto; `campaign-layout.spec.js` (IME → No facecam,
None → Auto, explicit Right survives a campaign change); harness 36/36.
