// 182 (Lane C Medium, owner rule): on a phone every visible control is ≥ 44 px tall, or its invisible hit area
// (::before/::after) is. Same mocked pages as the screenshot tour (shots.spec.js), Editor tabs included.
const { test, expect, job } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const camp = { slug: "ime-roleplay", name: "IME Roleplay X Motion Klip", brief_pending: false, platforms: ["tiktok", "instagram", "youtube"],
  default_layout: "none", sources: [], hashtags: ["#ime"], visibility: "shared", paused: false, can_edit: true, created_by_me: true,
  status: { code: "active", label: "Active", detail: "Week 2 · 6 days left" }, week: { id: "W2", days_left: 6 },
  payout_text: "Rp 200.000 per post at 40.000 views, max 2 per platform account/month", budget_text: "Rp 20.000.000/month",
  cap_meter: { label: "Your month: Rp 400.000 of Rp 2.400.000 cap", fraction: 0.17 },
  mine: { posted: 3, claimed: 2, paid: 1, planned: 1, paid_fmt: "Rp 200.000", expected_fmt: "Rp 200.000" } };
const clip = (o) => ({ job_id: "job-done", clip_index: 0, status: "review", title: null, manual_title: null, reason: "Reaksi panik lalu tawa.",
  start_time: 0, end_time: 40, duration_seconds: null, edit_spec: null, updated_at: "2026-10-07T10:00:00+00:00", campaign: "ime-roleplay",
  job_title: "Citer Molotov Ketemu KDM", job_date: "2026-10-05T10:00:00+07:00", job_status: "review", earn: null, rule_checks: [], ...o });
const editor = { job: { id: "job-done", title: "Mock finished stream", platform: "youtube_shorts", campaign: null, status: "review" },
  candidate: { id: "cand-a", status: "review", title: "First mock clip", reason: "Strong hook.", duration: 34, has_preview: false, has_final: false,
    preview_url: "/api/jobs/job-done/candidates/cand-a/preview", updated_at: "2026-10-05T10:00:00+00:00", edit_spec: {} },
  hook_title: { on: false, text: "", duration: 2.5, default_text: "First mock clip", durations: [2, 2.5, 3], max_chars: 80 },
  cuts: { trim: null, removed: [], output_seconds: 6, suggest_min_gap: 0.6, pad: 0.12 }, zoom: { on: true, intensity: 50, markers: [], max_markers: 40 },
  progress: { on: false, color: "#FFD60A", colors: ["#FFD60A"] }, audio: { compress: false, silence_trim: false, silence_ranges: [], loudness: { lufs: -14, true_peak_dbtp: -1, always_on: true } },
  thumbnail: { options: [], picked: null, locked: false, current_url: null, generating: false },
  watermark: { width: 320, opacity: 1, custom: false },
  export: { burn: true, description: "", submagic: { status: null, preview_url: null, error: null } },
  captions: { job: { style: "outline", animation: "karaoke", font: "Montserrat Black", size: 42 }, clip: null, style: "outline", animation: "karaoke",
    caption_y: null, auto_caption_y: 78, keywords: [], keyword_color: null, auto_keyword_color: "#30D158", transcript: "HAHAHAHA KEKUATAN", override: "",
    text: "HAHAHAHA KEKUATAN", burn: true, options: { styles: [{ id: "outline", label: "Outline", resting: "#FFFFFF", highlight: "#FFD60A", weight: 800,
    outline: 4.5, shadow: true, box: false, sizeMult: 1, letterSpacing: "0" }], animations: [{ id: "karaoke", label: "Karaoke sweep", family: "flow" }],
    presets: [{ id: "karaoke", label: "Karaoke", style: "outline", animation: "karaoke" }], fonts: ["Montserrat Black"],
    keyword_colors: [{ color: "#FFD60A", label: "Yellow" }], size_range: [12, 120], caption_y_range: [30, 85] } } };
const timeline = { version: 1, duration: 6, rate: 50, cached: true, peaks: Array.from({ length: 300 }, (_, i) => Math.abs(Math.sin(i / 9))),
  words: [{ i: 0, text: "Hahahaha", start: 0, end: 0.4 }, { i: 1, text: "Kekuatan", start: 0.5, end: 1.1 }], gaps: [] };
const row = (o) => ({ candidate_id: "cand-a", job_id: "job-done", job_title: "Mock stream", title: "Lompatan GILA", caption: "Gila banget\n\n#ime",
  caption_trimmed: false, hashtags: ["#ime"], platform: "tiktok", platform_name: "TikTok", duration: 34, rendered_at: null, has_thumbnail: false,
  filename: "x.mp4", post: null, campaign: "ime-roleplay", ...o });

async function seed(app, api) {
  api.campaigns = [camp];
  api.current = [job({ id: "job-run", status: "transcribing", progress: 40, source_title: "Live stream part 2", campaign: "ime-roleplay" }), job({ id: "job-done", status: "review", source_title: "Citer Molotov Ketemu KDM", campaign: "ime-roleplay" })];
  api.jobs = { ...api.jobs, "job-run": api.current[0] };   // the running job is polled
  api.publishGroups = [{ campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: [row({}), row({ platform: "youtube", platform_name: "YouTube Shorts" })] }];
  const now = new Date(), key = (d) => new Date(d.getTime() + 7 * 3600e3).toISOString().slice(0, 10);
  api.schedule = { from: now.toISOString(), now: now.toISOString(), posting_times: { tiktok: ["12:00"] }, overdue: [],
    days: [...Array(7)].map((_, i) => ({ date: key(new Date(Date.now() + i * 864e5)), posts: i ? [] : [{ id: "pl-1", candidate_id: "cand-a", job_id: "job-done",
      title: "Lompatan GILA", platform: "tiktok", platform_name: "TikTok", account_handle: "imeclips", status: "planned", campaign_name: "IME Roleplay",
      has_thumbnail: false, eligible: true, overdue: false, render: { state: "ready", label: "Final ready" }, scheduled_for: new Date(Date.now() + 2 * 3600e3).toISOString() }] })) };
  const f = (body) => (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  await app.route(/\/api\/review\/filter$/, f({ campaign: "ime-roleplay", job: "all", status: "to_review" }));
  await app.route(/\/api\/review\/clips\?/, f({ header: { kind: "campaign", title: "IME Roleplay X Motion Klip", status: { text: "Week 2 · 6 days left", ended: false }, to_review: 3 },
    clips: [clip({ id: "c94", score: 94, ai_title: "Best moment" }), clip({ id: "c88", score: 88, ai_title: "Second" }), clip({ id: "c71", score: 71, ai_title: "Third", earn: { code: "week_closed", label: "Week closed" } })] }));
  await app.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor\/timeline/, f(timeline));
  await app.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor(\?.*)?$/, f(editor));
  await app.reload();
}
const STEPS = [
  ["1-campaign", (a) => a.evaluate(() => window.showTab("campaign"))],
  ["3-analyze", (a) => a.evaluate(() => window.showTab("current"))],
  ["4-review", (a) => a.evaluate(() => { location.hash = "#review"; })],
  ["5-editor", (a) => a.evaluate(() => { location.hash = "#editor/job-done/cand-a"; })],
  ["5-editor-empty", (a) => a.evaluate(() => { location.hash = "#editor"; })],
  ["6-schedule", (a) => a.evaluate(() => { location.hash = ""; return window.showTab("schedule"); })],
  ["7-publish", (a) => a.evaluate(() => window.showTab("publish"))],
  ["8-track", (a) => a.evaluate(() => { location.hash = "#track"; })],
];

async function smallTargets(app) {
  return app.evaluate(() => {
    const hit = (e) => {
      const r = e.getBoundingClientRect(); let h = r.height;
      for (const p of ["::before", "::after"]) {
        const cs = getComputedStyle(e, p);
        if (cs.content === "none" || cs.position !== "absolute") continue;
        const top = parseFloat(cs.top) || 0, bottom = parseFloat(cs.bottom) || 0;
        h = Math.max(h, r.height - Math.min(0, top) - Math.min(0, bottom));
      }
      return h;
    };
    const vis = (e) => { const cs = getComputedStyle(e); return e.offsetParent && cs.visibility !== "hidden" && !e.closest("[inert],#island,.acct-menu:not(.open),.sheet-layer:not(.open),.job-overlay:not(.open)"); };
    return [...document.querySelectorAll("button,a[href],summary,select,[role=switch],[role=tab]")].filter(vis)
      .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && hit(e) < 43.5; })
      .map((e) => `${e.tagName.toLowerCase()}.${[...e.classList].join(".")} ${Math.round(e.getBoundingClientRect().height)}px "${(e.textContent || e.getAttribute("aria-label") || "").trim().slice(0, 20)}"`);
  });
}
test("phone: every control on every page has a ≥ 44 px touch target", async ({ app, api }) => {
  test.skip(test.info().project.name !== "mobile", "phone rule");
  test.setTimeout(90_000);
  await seed(app, api);
  const bad = {};
  for (const [name, go] of STEPS) {
    await go(app); await app.waitForTimeout(600);
    const s = await smallTargets(app); if (s.length) bad[name] = s;
    if (name === "5-editor") for (const tab of ["captions", "effects", "audio", "watermark", "thumbnail", "export"]) {
      const t = app.locator(`[data-ed-tab="${tab}"]`);
      await expect(t, "the Editor must render (mock in sync with editor.js)").toHaveCount(1);
      await t.click(); await app.waitForTimeout(300);
      const st = await smallTargets(app); if (st.length) bad[`${name}/${tab}`] = st;
    }
  }
  expect(bad).toEqual({});
});
