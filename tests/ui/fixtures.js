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
      sources: [], source_note: "", hashtags: ["#imeroleplay"] },
      { slug: "windah", name: "Windah", brief_pending: false, platforms: ["tiktok"], default_layout: "auto", default_language: "id",
        sources: [], source_note: "", hashtags: [] }],
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
      const temp = body?.password === "temporary pass1";
      if (body?.password !== "correct horse" && !temp) return json({ detail: "Wrong username or password" }, 401);
      api.user = { id: "u-1", username: body.username, role: "member" }; api.mustChange = temp;
      return json({ user: api.user, must_change_password: temp });
    }
    if (path === "/api/auth/password" && method === "POST" && api.mustChange !== undefined && !api.passwordRoute) {
      if (body?.current_password !== "temporary pass1") return json({ detail: "Current password is wrong" }, 400);
      api.mustChange = false; return json({ ok: true });
    }
    if (path === "/api/telegram" && method === "GET") return json(api.telegram || { bot_configured: true, bot_username: "clipflow_bot", chat_id: "", source: "none", ready: false });
    if (path === "/api/telegram" && method === "PUT") {
      if (body.chat_id && !/^(-?\d{3,20}|@[A-Za-z0-9_]{5,32})$/.test(body.chat_id)) return json({ detail: "Chat id: the number from @userinfobot" }, 400);
      api.telegram = { bot_configured: true, bot_username: "clipflow_bot", chat_id: body.chat_id, source: body.chat_id ? "user" : "none", ready: !!body.chat_id };
      return json(api.telegram);
    }
    if (path === "/api/telegram/test" && method === "POST") return json({ id: "tg-test", status: "queued" });
    if (path === "/api/publish/send-to-phone" && method === "POST") {
      if (!api.telegram?.ready) return json({ detail: "Add your Telegram chat id in Account first" }, 409);
      return json({ id: "tg-1", status: "queued" });
    }
    if (path === "/api/publish-queue" && method === "GET") return json({ groups: (api.publishGroups || []).map((g) => ({ ...g,
      cards: (g.cards || publishCards(g.rows, api)).map((c) => ({ ...c, earn: (api.cardEarn || {})[c.candidate_id] || c.earn || null, expired: !!g.expired })) })) });
    { const m = path.match(/^\/api\/posts\/([^/]+)$/);
      if (m && method === "PATCH") {
        const row = (api.publishGroups || []).flatMap((g) => g.rows).find((r) => r.post?.id === m[1]);
        if (!row && api.schedule) {   // P2.5 S3: a planned row in the Schedule view; posted/dropped leave it
          const all = [api.schedule.overdue, ...api.schedule.days.map((d) => d.posts)];
          const list = all.find((l) => l.some((x) => x.id === m[1]));
          if (list) { const i = list.findIndex((x) => x.id === m[1]); const x = list[i];
            if (["posted", "dropped"].includes(body.status)) list.splice(i, 1);
            return json({ ...x, ...body }); }
        }
        if (!row) return json({ detail: "Post not found" }, 404);
        if (body.status === "posted") Object.assign(row.post, { status: "posted", url: body.url, account_id: body.account_id || row.post.account_id, posted_at: iso(0) });
        const p = row.post;
        if (body.views != null) { p.views = body.views; p.views_at = iso(0); }
        if (body.status === "claimed") { p.status = "claimed"; p.claimed_views = p.views; p.expected_rp = 12000 * Math.floor(Math.min(p.views, 500000) / 3000); p.expected_fmt = "Rp " + p.expected_rp.toLocaleString("id-ID"); }
        if (body.status === "paid") { p.status = "paid"; p.paid_rp = body.paid_rp; p.paid_fmt = "Rp " + body.paid_rp.toLocaleString("id-ID");
          const d = body.paid_rp - p.expected_rp; p.paid_diff_fmt = d ? (d > 0 ? "+" : "−") + "Rp " + Math.abs(d).toLocaleString("id-ID") : null; }
        return json(p);
      } }
    if (path === "/api/posts" && method === "POST") {
      const row = (api.publishGroups || []).flatMap((g) => g.rows).find((r) => r.candidate_id === body.candidate_id && r.platform === body.platform);
      const acc = (api.accounts || []).find((a) => a.id === body.account_id);
      const post = { id: "post-1", candidate_id: body.candidate_id, platform: body.platform, account_id: body.account_id, account_handle: acc?.handle,
        status: body.status, url: body.url, posted_at: iso(0),
        eligible: !(row?.checks || []).some((c) => c.level === "warn" && (!c.account_id || c.account_id === body.account_id)),
        ineligible_reason: (row?.checks || []).filter((c) => c.level === "warn" && (!c.account_id || c.account_id === body.account_id)).map((c) => c.message).join("; ") || null };
      if (row) row.post = post;
      return json(post);
    }
    if (path === "/api/accounts" && method === "GET") return json({ accounts: api.accounts || [], platforms: [
      { slug: "facebook", name: "Facebook Reels" }, { slug: "instagram", name: "Instagram Reels" }, { slug: "youtube", name: "YouTube Shorts" }, { slug: "tiktok", name: "TikTok" }] });
    if (path === "/api/accounts" && method === "POST") {
      if ((api.accounts || []).some((a) => a.platform === body.platform && a.handle.toLowerCase() === body.handle.toLowerCase())) return json({ detail: `You already have @${body.handle} on this platform` }, 409);
      const a = { id: "acc-" + body.handle, platform: body.platform, platform_name: body.platform, handle: body.handle, note: body.note, active: true, created_at: iso(0) };
      api.accounts = [...(api.accounts || []), a]; return json(a);
    }
    { const m = path.match(/^\/api\/accounts\/([^/]+)$/);
      if (m) { const a = (api.accounts || []).find((x) => x.id === m[1]); if (!a) return json({ detail: "Account not found" }, 404);
        if (method === "PATCH") { Object.assign(a, body); return json(a); }
        if (method === "DELETE") {
          if (a.posts) { a.active = false; return json({ ok: true, paused: true, detail: `Paused instead of removed: ${a.posts} posts use this account` }); }
          api.accounts = api.accounts.filter((x) => x !== a); return json({ ok: true }); } } }
    if (path === "/api/admin/users" && method === "GET") return json({ users: api.users || [] });
    if (path === "/api/admin/users" && method === "POST") {
      if ((api.users || []).some((u) => u.username === body.username)) return json({ detail: `Username '${body.username}' is taken` }, 409);
      const u = { id: "u-" + body.username, username: body.username, role: body.role, active: true, must_change_password: true, created_at: iso(0), last_seen_at: null, jobs: 0, tokens: 0 };
      api.users = [...(api.users || []), u]; return json(u);
    }
    { const m = path.match(/^\/api\/admin\/users\/([^/]+)(\/reset-password)?$/);
      if (m) {
        const u = (api.users || []).find((x) => x.id === m[1]);
        if (!u) return json({ detail: "User not found" }, 404);
        if (m[2]) { u.must_change_password = true; return json({ ok: true, must_change_password: true }); }
        const admins = api.users.filter((x) => x.role === "admin" && x.active);
        const role = body.role ?? u.role, active = body.active ?? u.active;
        if (u.role === "admin" && u.active && (role !== "admin" || !active) && admins.length <= 1)
          return json({ detail: "Can't disable or demote yourself: the last active admin. Make another admin first." }, 409);
        Object.assign(u, { role, active }); return json(u);
      } }
    if (path === "/api/auth/logout") { api.user = null; return json({ ok: true }); }
    if (path === "/api/auth/tokens" && method === "GET") return json({ tokens: api.tokens || [] });
    if (path === "/api/auth/tokens" && method === "POST") {
      const t = { id: "tok-" + ((api.tokens || []).length + 1), name: body?.name, prefix: "cf_mock123", created_at: iso(0), last_used_at: null };
      api.tokens = [t, ...(api.tokens || [])];
      return json({ ...t, token: "cf_mock123-full-secret" });
    }
    { const m = path.match(/^\/api\/auth\/tokens\/([^/]+)$/);
      if (m && method === "DELETE") { api.tokens = (api.tokens || []).filter((t) => t.id !== m[1]); return json({ ok: true }); } }
    if (path === "/api/campaigns/parse-brief" && method === "POST") return json(api.parsedBrief);   // P3 part 4 mocks (166)
    if (path === "/api/campaigns/preview" && method === "POST") return json({ payout_text: "Preview: " + (body.rules.platforms || []).join(","), view: { payout: [], weeks: [] } });
    if (path === "/api/campaigns" && method === "POST") {
      const open = (body.unsure || []).map((u) => u.field).filter((f) => !body.confirmed.includes(f));
      if (open.length) return json({ detail: "Confirm these first: " + open.join(", ") }, 409);
      api.createdCampaign = body;
      api.campaignDetail = { ...(api.campaignDetail || {}), [body.slug]: { slug: body.slug, name: body.name, status: { code: "active", label: "Active", detail: "" }, mine: {}, view: {}, brief_text: body.brief_text, can_edit: true } };
      return json(api.campaignDetail[body.slug], 201);
    }
    { const m = path.match(/^\/api\/campaigns\/([^/]+)(\/watermark)?$/);   // P3 part 5 mocks
      if (m && m[2]) return route.fulfill({ status: 200, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "base64") });
      if (m && method === "GET") { const d = (api.campaignDetail || {})[m[1]]; return d ? json(d) : json({ detail: "Campaign not found" }, 404); }
      if (m && method === "PUT") { const d = (api.campaignDetail || {})[m[1]]; Object.assign(d, body, body.paused != null ? { status: { ...d.status, code: body.paused ? "paused" : "active", label: body.paused ? "Paused" : "Active" } } : {}); return json(d); } }
    if (path === "/api/schedule" && method === "GET") return json(api.schedule || { overdue: [], days: [], posting_times: {} });   // P2.5 S3
    { const m = path.match(/^\/api\/jobs\/([^/]+)\/candidates\/([^/]+)\/(schedule-plan|schedule)$/);   // P2.5 S2 mocks
      if (m && m[3] === "schedule-plan" && method === "GET") return json(api.schedulePlan);
      if (m && m[3] === "schedule" && method === "POST") {
        if (body.dry_run) return json({ posts: body.posts.map((x) => ({ platform: x.platform, eligible: !(api.planWarn || {})[x.platform],
          ineligible_reason: (api.planWarn || {})[x.platform] || null })) });
        return json({ approved: !api.schedulePlan.approved, posts: body.posts.map((x, i) => ({ id: "plan-" + i, status: "planned", ...x })) });
      } }
    if (path === "/api/settings" && method === "PUT" && body?.values && "REMINDER_LEAD_MIN" in body.values) {   // P2.5 S4 mock
      api.settings = { ...(api.settings || {}), REMINDER_LEAD_MIN: { value: body.values.REMINDER_LEAD_MIN, source: "user", scope: "user" } };
      if (!("POSTING_TIMES" in body.values)) return json({ status: "ok" });
    }
    if (path === "/api/settings" && method === "PUT" && body?.values && "POSTING_TIMES" in body.values) {   // P2.5 S1 mock
      const v = body.values.POSTING_TIMES;
      if (v.includes("99:")) return json({ detail: "TikTok: '99:00' is not a time (HH:MM, 24 h)" }, 400);
      api.settings = { ...(api.settings || {}), POSTING_TIMES: { value: v || api.defaultPostingTimes, source: v ? "user" : "default", scope: "user" } };
      return json({ status: "ok" });
    }
    if (method === "GET" && path === "/api/auth/me") return api.user ? json({ user: api.user, via: "session", must_change_password: !!api.mustChange }) : json({ detail: "Unauthorized" }, 401);
    if (method === "GET") {
      if (path === "/api/media-token") return json({ token: "mock-token", expires_at: iso(-720) });
      if (path === "/api/settings") return json(api.settings || {});
      if (path === "/api/campaigns") return json(api.campaigns);
      if (path === "/api/analysis-estimate") return json(api.estimate || { samples: 0 });
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

// 149: the stepper's Review opens the Review page; the old job list + drawer ("All edits") is opened directly.
async function classicQueue(page) {
  await page.evaluate(async () => { window.clipflowReview?.close(); history.replaceState(null, "", location.pathname); await window.showTab("queue"); });
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

// Mock of the server's per-clip cards (144): one per candidate in row order; summary = live posts / platforms,
// expected_fmt from api.cardExpected[cid] (the real server formats it with payouts).
function publishCards(rows, api) {
  const out = [];
  for (const r of rows || []) {
    let c = out.find((x) => x.candidate_id === r.candidate_id);
    if (!c) { c = { candidate_id: r.candidate_id, job_id: r.job_id, job_title: r.job_title, title: r.title, caption: r.caption,
      has_thumbnail: r.has_thumbnail, filename: (r.campaign || "clip") + "_" + r.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".mp4",
      platforms: [], summary: { posted: 0, total: 0, expected_fmt: (api.cardExpected || {})[r.candidate_id] || null },
      last_send: (api.cardSends || {})[r.candidate_id] || null }; out.push(c); }
    c.platforms.push(r.platform); c.summary.total++;
    if (r.post && ["posted", "claimed", "paid"].includes(r.post.status)) c.summary.posted++;
  }
  return out;
}

module.exports = { test, expect: base.expect, job, candidate, nav, blockingProblems, mockApi, newState, classicQueue };
