// Shared fixtures: `app` = the page with /api mocked from a mutable `api` state, loaded and settled.
// Tests change `api.current` / `api.queue` / `api.jobs` and wait for the 2.2 s poll to pick it up.
// Every request the app makes is recorded in `api.calls`; page errors fail the test.
const base = require("@playwright/test");

const iso = (min = 0) => new Date(Date.now() - min * 60_000).toISOString();

function job(over = {}) {
  const id = over.id || "job-" + Math.random().toString(36).slice(2, 10);
  return {
    id, source_video_id: "vid-" + id, youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    source_title: "Mock stream " + id, custom_title: null, job_type: "analysis", status: "completed",
    progress: 100, message: "Done", error_stage: null, error_message: null, created_at: iso(30),
    started_at: iso(29), completed_at: iso(5), review_ready_at: iso(5), layout: "auto",
    platform: "youtube_shorts", split_ratio: 70,
    subtitle_style: { bold: true, font: "Montserrat Black", size: 72, color: "#FFFFFF", style: "bold",
      outline: 4, position: "bottom", animation: "karaoke" },
    subtitle_font: "Montserrat Black", subtitle_size: 72, subtitle_animation: "karaoke",
    watermark_width: null, watermark_opacity: null, burn_subtitles: null, attempts: 0, error_class: null,
    retry_after: null, watermark_position_y: 25, subtitle_seam_gap: 1.5, language: "auto",
    detected_language: "id", language_confidence: 0.98, effective_language: "id", campaign: null,
    candidates: [], ...over,
  };
}

function candidate(jobId, over = {}) {
  const id = over.id || "cand-" + Math.random().toString(36).slice(2, 10);
  return {
    id, job_id: jobId, clip_index: 0, start_time: 26, end_time: 60, duration_seconds: 34,
    reason: "Strong hook in the first 2 s.", ai_title: "Mock clip title", title: null, manual_title: null,
    subtitle_segments: [{ start: 0, end: 2, text: "MOCK CAPTION LINE",
      words: [{ word: "MOCK", start: 0, end: 0.6 }, { word: "CAPTION", start: 0.6, end: 1.3 }, { word: "LINE", start: 1.3, end: 2 }] }],
    subtitle_override: null, subtitle_text: "MOCK CAPTION LINE", content_type: "Funny", rating: null,
    score: 8, status: "review", progress: 100, message: "Preview ready", error_message: null,
    error_stage: null, face_crop: {}, preview_path: "/data/previews/" + id + ".mp4", render_path: null,
    final_path: null, thumbnail_path: "/data/previews/" + id + ".jpg", rendered_at: null,
    created_at: iso(10), updated_at: iso(10), description: null, thumbnail_options: null,
    thumbnail_locked: false, submagic_project_id: null, submagic_status: null,
    submagic_preview_url: null, submagic_download_url: null, submagic_error: null,
    hook_provider: "gemini", heartbeat_at: null, attempts: 0, error_class: null, retry_after: null, ...over,
  };
}

function newState() {
  const done = job({ id: "job-done", status: "review", source_title: "Mock finished stream" });
  done.candidates = [candidate(done.id, { id: "cand-a", ai_title: "First mock clip" }),
                     candidate(done.id, { id: "cand-b", clip_index: 1, ai_title: "Second mock clip" })];
  return {
    user: { id: "u-admin", username: "admin", role: "admin" }, // P1.5: signed in unless a test clears it
    current: [], queue: [done], jobs: { [done.id]: done }, calls: [],
    campaigns: [{ slug: "ime-roleplay", name: "IME Roleplay", brief_pending: false, platforms: ["tiktok"], default_layout: "none",
      sources: [], source_note: "", hashtags: ["#imeroleplay"] }],
  };
}

async function mockApi(page, api) {
  await page.route(/^https:\/\/i\.ytimg\.com\//, (r) => r.abort());
  await page.route("**/api/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname, method = req.method();
    let body = null;
    try { body = req.postDataJSON(); } catch { body = req.postData(); }
    api.calls.push({ method, path, search: url.search, body });
    const json = (data, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (path === "/api/auth/login" && method === "POST") {
      if (body?.password !== "correct horse") return json({ detail: "Wrong username or password" }, 401);
      api.user = { id: "u-1", username: body.username, role: "member" };
      return json({ user: api.user });
    }
    if (path === "/api/auth/logout") { api.user = null; return json({ ok: true }); }
    if (method === "GET" && path === "/api/auth/me") return api.user ? json({ user: api.user, via: "session" }) : json({ detail: "Unauthorized" }, 401);
    if (method === "GET") {
      if (path === "/api/media-token") return json({ token: "mock-token", expires_at: iso(-720) });
      if (path === "/api/settings") return json({});
      if (path === "/api/campaigns") return json(api.campaigns);
      if (path === "/api/activity") return json({ items: api.activity || [] }); // 090 island feed
      if (path === "/api/assets/watermarks") return json({ assets: [] });
      if (path === "/api/jobs") return json(url.searchParams.get("scope") === "queue" ? api.queue : api.current);
      const m = path.match(/^\/api\/jobs\/([^/]+)$/);
      if (m) return api.jobs[m[1]] ? json(api.jobs[m[1]]) : json({ detail: "Not found" }, 404);
      if (/\/versions$/.test(path)) return json({ versions: [] });
      return json({ detail: "mock: no fixture for " + path }, 404); // thumbnails, previews, …
    }
    if (method === "POST" && path === "/api/jobs") {
      const j = job({ id: "job-new", status: "queued", progress: 0, message: "Queued", youtube_url: body?.youtube_url });
      api.current = [...api.current, j]; api.jobs[j.id] = j;
      return json(j);
    }
    return json({ ok: true }); // other writes: accepted, recorded in api.calls, nothing happens
  });
}

const test = base.test.extend({
  api: async ({}, use) => { await use(newState()); },
  app: async ({ page, api }, use) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|404/.test(m.text())) errors.push("console: " + m.text()); });
    page.on("dialog", (d) => { errors.push("unexpected dialog: " + d.message()); d.dismiss(); });
    await mockApi(page, api);
    await page.goto("/");
    await page.waitForFunction(() => document.readyState === "complete");
    await page.waitForResponse((r) => r.url().includes("/api/jobs?scope=current"));
    await use(page);
    base.expect(errors, "page errors / dialogs during the test").toEqual([]);
  },
});

// Visible nav item (sidebar on desktop, bottom tab bar at ≤ 600 px).
async function nav(page, name) {
  await page.locator(`[data-nav="${name}"]:visible`).first().click();
}

// The "nothing is clickable" regression (CLAUDE.md: every closed overlay layer must be
// visibility:hidden + pointer-events:none). Returns the problems found (empty = fine):
// 1) a closed layer that would still catch clicks, 2) a probe control covered by something else.
async function blockingProblems(page, probes) {
  return page.evaluate((probes) => {
    const out = [];
    const catches = (el) => {
      const cs = getComputedStyle(el);
      return cs.display !== "none" && cs.visibility !== "hidden" && cs.pointerEvents !== "none" && !el.hidden;
    };
    const closed = [
      ...[...document.querySelectorAll(".sheet-layer:not(.open)")],
      ...[...document.querySelectorAll("#jobOverlay:not(.open)")],
      ...(document.body.classList.contains("sidebar-open") ? [] : [document.getElementById("sidebarScrim")]),
      ...[...document.querySelectorAll("#versionPopover:not(.open)")],
    ].filter(Boolean);
    for (const el of closed) if (catches(el)) out.push("closed layer still catches clicks: #" + (el.id || el.className));
    for (const sel of probes) {
      const el = [...document.querySelectorAll(sel)].find((e) => e.offsetParent !== null || getComputedStyle(e).position === "fixed");
      if (!el) { out.push("probe not visible: " + sel); continue; }
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) { out.push("probe has no size: " + sel); continue; }
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (y < 0 || y > innerHeight || x < 0 || x > innerWidth) continue; // off-screen: not a blocker
      const hit = document.elementFromPoint(x, y);
      if (!hit || !(el === hit || el.contains(hit)))
        out.push(`${sel} covered by ${hit ? hit.tagName.toLowerCase() + (hit.id ? "#" + hit.id : "") + "." + [...hit.classList].join(".") : "nothing"}`);
    }
    return out;
  }, probes);
}

module.exports = { test, expect: base.expect, job, candidate, nav, blockingProblems, mockApi, newState };
