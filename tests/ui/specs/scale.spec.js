// UI task phase 1 item 1 (×1.2 scale): no page, sheet or menu scrolls sideways at 390×844 or 1280×700, and nothing
// visible sticks out past the right edge. Mocked API (seed copied from shots.spec.js).
const { test, expect, job } = require("../fixtures");

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
  progress: { on: false, color: "#FFD60A", colors: ["#FFD60A"] }, audio: { compress: false, loud: false, silence_trim: false, silence_ranges: [], loudness: { lufs: -14, true_peak_dbtp: -1, always_on: true } },
  thumbnail: { options: [], picked: null, locked: false, current_url: null, generating: false },
  watermark: { width: 320, opacity: 1, custom: false },
  export: { burn: true, description: "", submagic: { status: null, preview_url: null, error: null } },
  director: { items: [], rendered: ["emoji", "flash", "freeze", "punch", "push", "shake", "slowmo", "whip", "zoom_out"], arrives_in: {}, min_gap: 3, frames_ready: false, vision_on: true,
      effects: ["punch", "push", "zoom_out", "shake", "flash", "whip", "freeze", "slowmo", "emoji"], defaults: { emoji: { emoji: "😂" }, freeze: { hold: 0.6 }, slowmo: { dur: 1.2, factor: 0.5 } },
      sfx: ["whoosh", "boom", "bass_hit", "ding", "record_scratch", "laugh"], emoji: ["😂", "😭", "💀"] },
    look: { preset: "none", vignette: false, grain: false, presets: ["none", "vivid_gaming", "warm", "moody"] },
    pack: { id: "podcast_clean", name: "Podcast Clean", from_campaign: true, options: [{ id: "gaming_hype", name: "Gaming Hype", min_gap: 3 },
      { id: "funny_meme", name: "Funny / Meme", min_gap: 3 }, { id: "drama_tension", name: "Drama / Tension", min_gap: 5 }, { id: "podcast_clean", name: "Podcast Clean", min_gap: 6 }] },
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
  ["2-import", (a) => a.evaluate(() => { location.hash = "#import"; })],
  ["3-analyze", (a) => a.evaluate(() => window.showTab("current"))],
  ["4-review", (a) => a.evaluate(() => { location.hash = "#review"; })],
  ["5-editor", (a) => a.evaluate(() => { location.hash = "#editor/job-done/cand-a"; })],
  ["6-schedule", (a) => a.evaluate(() => { location.hash = ""; return window.showTab("schedule"); })],
  ["7-publish", (a) => a.evaluate(() => window.showTab("publish"))],
  ["8-track", (a) => a.evaluate(() => { location.hash = "#track"; })],
];

async function overflow(app) {
  return app.evaluate(() => {
    const W = innerWidth, out = [];
    if (document.documentElement.scrollWidth > W + 1) out.push(`page scrollWidth ${document.documentElement.scrollWidth} > ${W}`);
    for (const e of document.querySelectorAll("body *")) {
      const cs = getComputedStyle(e);
      if (!e.offsetParent && cs.position !== "fixed") continue;
      if (cs.visibility === "hidden" || e.closest(".sheet-layer:not(.open),.acct-menu:not(.open),.job-overlay:not(.open),#island,[hidden],details:not([open]) > :not(summary)")) continue;   // closed <details> content isn't shown
      const r = e.getBoundingClientRect();
      if (r.width && r.right > W + 1 && !e.closest("[data-hscroll],.ed-tlwrap,.ed-tl,.rv-filters,.flow-pill") && getComputedStyle(e.parentElement).overflowX === "visible")
        out.push(`${e.tagName.toLowerCase()}.${[...e.classList].join(".")} right ${Math.round(r.right)}`);
    }
    return out.slice(0, 8);
  });
}
// item 3: scrolled to the bottom, the last content of every page ends above the dock (+ a gap)
async function underDock(app) {
  await app.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await app.waitForTimeout(300);
  return app.evaluate(() => {
    const dock = document.getElementById("flowNav").getBoundingClientRect(), out = [];
    for (const e of document.querySelectorAll("main *")) {
      const cs = getComputedStyle(e);
      if (!e.offsetParent || cs.position === "fixed" || cs.position === "sticky" || e.closest(".sheet-layer,.ed-foot,[hidden],.hidden,details:not([open]) > :not(summary)")) continue;
      if (e.children.length) continue;                       // leaves only: text, buttons, images
      const r = e.getBoundingClientRect();
      if (r.height && r.width && r.bottom > dock.top - 12 && r.top < dock.bottom && r.right > dock.left - 40 && r.left < dock.right + 40)   // ≥ 12 px clear of the dock (its shadow + glass edge)
        out.push(`${e.tagName.toLowerCase()}.${[...e.classList].join(".")} bottom ${Math.round(r.bottom)} > dock ${Math.round(dock.top)}`);
    }
    return out.slice(0, 5);
  });
}
for (const [w, h] of [[390, 844], [1280, 800]]) {
  test(`nothing hides under the dock at ${w}×${h}`, async ({ app, api }, info) => {
    test.skip((w === 390) !== (info.project.name === "mobile"), "one size per project");
    test.setTimeout(120_000);
    await app.setViewportSize({ width: w, height: h });
    await seed(app, api);
    api.current = Array.from({ length: 12 }, (_, i) => job({ id: "s" + i, status: "review", source_title: "Stream " + i }));
    api.jobs = { ...api.jobs, ...Object.fromEntries(api.current.map((j) => [j.id, j])) };
    // long pages: 9 review clips, 6 publish cards, a post on every schedule day
    api.publishGroups = [{ campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: Array.from({ length: 6 }, (_, i) => row({ candidate_id: "c" + i, title: "Clip " + i })) }];
    api.schedule.days.forEach((d, i) => { if (!d.posts.length) d.posts = [{ ...api.schedule.days[0].posts[0], id: "pl-" + i, title: "Planned " + i }]; });
    await app.route(/\/api\/review\/clips\?/, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      header: { kind: "campaign", title: "IME Roleplay X Motion Klip", status: { text: "Week 2", ended: false }, to_review: 9 },
      clips: Array.from({ length: 9 }, (_, i) => clip({ id: "r" + i, score: 90 - i, ai_title: "Clip " + i })) }) }));
    await app.reload();
    const bad = {};
    for (const [name, go] of STEPS) {
      if (name === "5-editor") continue;                     // the Editor fits the window above the dock (its own layout)
      await go(app); await app.waitForTimeout(700);
      const o = await underDock(app); if (o.length) bad[name] = o;
    }
    expect(bad).toEqual({});
  });
}

for (const [w, h] of [[390, 844], [1280, 700]]) {
  test(`no horizontal overflow at ${w}×${h}`, async ({ app, api }, info) => {
    test.skip((w === 390) !== (info.project.name === "mobile"), "one size per project");
    test.setTimeout(120_000);
    await app.setViewportSize({ width: w, height: h });
    await seed(app, api);
    const bad = {};
    for (const [name, go] of STEPS) {
      await go(app); await app.waitForTimeout(600);
      const o = await overflow(app); if (o.length) bad[name] = o;
    }
    await app.evaluate(() => { location.hash = ""; return window.showTab("current"); });
    await app.click("#accountMenuBtn"); await app.waitForTimeout(400);
    let o = await overflow(app); if (o.length) bad.menu = o;
    await app.keyboard.press("Escape");
    if (!(await app.locator('#toolbar .icon-btn[data-nav="settings"]').isVisible())) await app.click("#accountMenuBtn");
    await app.locator('[data-nav="settings"] >> visible=true').first().click(); await app.waitForTimeout(700);
    o = await overflow(app); if (o.length) bad.settings = o;
    expect(bad).toEqual({});
  });
}
