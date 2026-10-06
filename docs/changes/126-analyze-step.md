# 126 · Analyze step rebuilt as flow-preview step 3 "New job options" (same POST /api/jobs payload) · index.html, main.py, shared/campaigns.py, docs/roadmap.md

- **Form:** eyebrow "Step 3 · Analyze" + "New job options"; Video (validation, hint and thumbnail preview unchanged),
  optional Job name; Campaign select + Language segmented control (Auto-detect / English / Indonesian) with a hint
  line; Layout cards like the mock: "Gameplay + facecam" (reveals Game : cam 60:40 / 70:30 and Cam position
  Auto/Left/Right) and "Full frame" (= layout none), plus disabled "Coming soon" cards Speaker follow, Two-speaker
  stacked, Wide + blur (roadmap P4 · Layouts); Output platform segmented (YouTube Shorts / Reels / TikTok);
  "Subtitles: style · font · size · karaoke · Change in Settings" (Settings gains a "Subtitle defaults" group for
  the user-level DEFAULT_SUBTITLE_* keys); "Start analysis" + estimate. The Options `<details>` is gone.
- **Campaign defaults:** `default_layout` (117) and new `default_language` (explicit `language` / `title.language`
  in the rules, else none = keep Auto) pre-fill the form with a "from campaign" tag until you pick one yourself;
  a campaign-filled language is not stored as your last explicit language (language_fallback).
  Today: IME → Full frame + Indonesian, Windah → Indonesian, Fandra → unchanged (Auto).
- **Estimate:** `GET /api/analysis-estimate` (own jobs, last 20 finished with a transcript): median processing
  rate × median video length → "≈ N min for a 1 h 24 min video"; hidden with no history.
- **Payload:** identical keys/values (`analyze.spec.js` pins the default payload and a full-option one).
- The "Gameplay + facecam" illustration shows ClipFlow's real output (game top, cam panel bottom), not the mock's.

**Verified:** harness 66 passed (import, campaign defaults incl. language, analyze: payloads, Full frame ↔ facecam
options, disabled cards, estimate, subtitle line → Settings); screenshots vs mock at 1280 and 390 (light);
prod read-only: estimate {samples 20, ≈ 4 min for a 6 min video}, campaigns expose default_language.
