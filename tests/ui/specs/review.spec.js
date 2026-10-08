// Review page (lane B, P4 task 6 + filters): flow-preview step 4 as its own view. Mock mode:
// /api/review/filter and /api/review/clips are answered here (the server sorts and computes chips/earn).
const { test, expect, job } = require("../fixtures");

const ok = (id, label) => ({ id, ok: true, blocking: true, label, detail: "", fix: null });
const clip = (o) => ({ job_id: "job-a", clip_index: 0, status: "review", title: null, manual_title: null, reason: "Strong hook, then a payoff.",
  start_time: 0, end_time: 40, duration_seconds: null, edit_spec: null, updated_at: "2026-10-07T10:00:00+00:00", campaign: "ime-roleplay",
  job_title: "Citer Molotov Ketemu KDM", job_date: "2026-10-05T10:00:00+07:00", job_status: "review", earn: null, rule_checks: [], ...o });

const IME = [
  clip({ id: "c94", score: 94, ai_title: "Best", reason: "Reaksi panik lalu tawa, ditutup tebakan lucu.", rule_checks: [ok("length", "Length 40 s"), ok("hashtags", "Hashtags")] }),
  clip({ id: "c88", score: 88, ai_title: "Too long", job_id: "job-b", job_title: "Second stream", end_time: 96,
         rule_checks: [{ id: "length", ok: false, blocking: true, label: "Length 96 s: too long for Facebook Reels (3–90 s)", detail: "", fix: "trim", fix_target: 88 }] }),
  clip({ id: "c63", score: 63, ai_title: "No tags", rule_checks: [{ id: "hashtags", ok: false, blocking: true, label: "Hashtags missing or out of order", detail: "", fix: "hashtags" }] }),
  clip({ id: "c71", score: 71, ai_title: "Closed week", earn: { code: "week_closed", label: "Week closed" }, rule_checks: [ok("length", "Length 39 s")] }),
];
const EXPIRED = clip({ id: "c50", score: 99, ai_title: "From an ended campaign", expired: true, earn: { code: "campaign_ended", label: "Campaign ended" } });

async function mockReview(page, api, { filter = { campaign: "ime-roleplay", job: "all", status: "to_review" } } = {}) {
  api.filter = filter;
  api.queue = [job({ id: "job-a", status: "review", source_title: "Citer Molotov Ketemu KDM", campaign: "ime-roleplay" }),
               job({ id: "job-b", status: "review", source_title: "Second stream", campaign: "ime-roleplay" }),
               job({ id: "job-c", status: "review", source_title: "No campaign video", campaign: null })];
  await page.route(/\/api\/review\/filter$/, async (route) => {
    if (route.request().method() === "PUT") { api.filter = route.request().postDataJSON(); api.calls.push({ method: "PUT", path: "/api/review/filter", body: api.filter }); }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api.filter) });
  });
  await page.route(/\/api\/review\/clips\?/, (route) => {
    const q = new URL(route.request().url()).searchParams, campaign = q.get("campaign"), jobId = q.get("job");
    api.calls.push({ method: "GET", path: "/api/review/clips", query: Object.fromEntries(q) });
    let clips = campaign === "ime-roleplay" ? IME : [];
    if (jobId !== "all") clips = clips.filter((c) => c.job_id === jobId);
    const header = jobId !== "all" ? { kind: "job", title: clips[0]?.job_title || "No campaign video" }
      : campaign === "ime-roleplay" ? { kind: "campaign", title: "IME Roleplay X Motion Klip", status: { text: "Week 2 · 6 days left", ended: false } }
      : { kind: campaign, title: campaign === "none" ? "Clips without a campaign" : "All clips" };
    return route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ header: { ...header, to_review: clips.filter((c) => c.status === "review").length }, clips }) });
  });
}

async function open(app, api, opts) {
  await mockReview(app, api, opts);
  await app.evaluate(() => { location.hash = "#review"; });
  await expect(app.locator("#rvFilters select").first()).toBeVisible();
}

test.describe("Review page", () => {
  // QA 649ae25 Low 1: html{scroll-behavior:smooth} made clicks "not stable" on mobile; reduced motion = instant scroll
  test.use({ reducedMotion: "reduce" });
  test("campaign + all jobs: one grid across jobs, campaign header, source labels, earn last", async ({ app, api }) => {
    await open(app, api);
    await expect(app.locator(".rv-eyebrow")).toHaveText("Step 4 · Review");
    await expect(app.locator(".rv-title")).toHaveText("IME Roleplay X Motion Klip");
    await expect(app.locator(".rv-camp-status")).toHaveText("IME Roleplay · Week 2 · 6 days left");
    await expect(app.locator(".rv-desc").first()).toHaveText("Clips are sorted by hook score. A clip can be scheduled only when every campaign rule passes.");
    await expect(app.locator("#rvCount")).toHaveText("4 to review");
    await expect(app.locator(".rv-score")).toHaveText(["Hook 94", "Hook 88", "Hook 63", "Hook 71"]);   // server order, earn last
    await expect(app.locator(".rv-src").nth(1)).toContainText("Second stream ·");
    await expect(app.locator(".rv-clip").nth(3)).toHaveClass(/no-earn/);
    await expect(app.locator(".rv-clip").nth(3).locator(".rv-earn")).toHaveText("Week closed");
    await expect(app.locator(".rv-reason b").first()).toHaveText("Reaksi panik lalu tawa");
    await expect(app.locator(".rv-fix")).toHaveText(["Trim to 88 s", "Add tags"]);
    expect(await app.locator("[data-rv-approve]").evaluateAll((b) => b.map((x) => !x.disabled))).toEqual([true, false, false, true]);
    await expect(app.locator(".rv-open").nth(1)).toHaveAttribute("href", "#editor/job-b/c88");
  });

  test("filters change the query and are saved per user; job filter shows the job header", async ({ app, api }) => {
    await open(app, api);
    await app.locator('[data-rv-status="approved"]').click();
    await expect.poll(() => api.calls.filter((c) => c.path === "/api/review/clips").at(-1)?.query.status).toBe("approved");
    await expect.poll(() => api.filter.status, { timeout: 3000 }).toBe("approved");
    await app.locator('[data-rv-status="to_review"]').click();
    await app.locator('select[data-rv-filter="job"]').selectOption("job-b");
    await expect(app.locator(".rv-title")).toHaveText("Second stream");
    await expect(app.locator(".rv-src")).toHaveCount(0);                                    // single job: no source label
    await expect(app).toHaveURL(/#review\/job-b$/);
    await expect.poll(() => api.filter.job, { timeout: 3000 }).toBe("job-b");
  });

  test("remembered filter is applied on open; empty state per filter", async ({ app, api }) => {
    await open(app, api, { filter: { campaign: "none", job: "all", status: "to_review" } });
    await expect(app.locator('select[data-rv-filter="campaign"]')).toHaveValue("none");
    await expect(app.locator(".rv-empty-title")).toHaveText("No no-campaign clips to review.");
    await app.locator('select[data-rv-filter="campaign"]').selectOption("ime-roleplay");
    await app.locator('[data-rv-status="all"]').click();
    await expect(app.locator(".rv-clip")).toHaveCount(4);
  });

  test("quick fixes + approve use each clip's own job", async ({ app, api }) => {
    await open(app, api);
    await app.locator(".rv-fix", { hasText: "Trim to 88 s" }).click();
    await expect.poll(() => api.calls.find((c) => c.method === "PUT" && c.path.endsWith("/job-b/candidates/c88/editor/fix-length"))?.body).toEqual({ target: 88 });
    await app.locator(".rv-fix", { hasText: "Add tags" }).click();
    await expect.poll(() => api.calls.find((c) => c.method === "POST" && c.path.endsWith("/job-a/candidates/c63/fix-rule"))?.body).toEqual({ rule: "hashtags" });
    await app.locator("[data-rv-approve]").first().click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path.endsWith("/job-a/candidates/c94/approve"))).toBe(true);
  });

  test("2 columns on desktop, 1 on mobile; no horizontal scroll", async ({ app, api }, info) => {
    await open(app, api);
    const cols = await app.locator("#rvGrid").evaluate((g) => getComputedStyle(g).gridTemplateColumns.split(" ").length);
    expect(cols).toBe(info.project.name === "mobile" ? 1 : 2);
    expect(await app.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });
});

// 149 (lane-b production merge): the stepper's Review opens this page, "All edits" opens the old panel for that
// clip (caption styles, thumbnails, … until they move into the Editor), the Editor page lights the Editor step.
test.describe("Review/Editor navigation (149)", () => {
  test.use({ reducedMotion: "reduce" });
  test("stepper Review → page; All edits → old panel; Open editor → Editor step; Editor step reopens it", async ({ app, api }) => {
    await mockReview(app, api);
    await app.locator('#flow [data-nav="queue"]').click();
    await expect(app.locator("#rvFilters select").first()).toBeVisible();
    await expect(app.locator("#queueSection")).toBeHidden();
    await expect(app.locator('[data-approve-schedule="job-a"][data-cid="c94"]')).toHaveText("Approve & schedule");
    await expect(app.locator('[data-approve-schedule][data-cid="c63"]')).toHaveCount(0);       // blocked clip: no schedule
    await app.locator(".rv-open").first().click();
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Editor");
    await expect(app.locator("#pageTitle")).toHaveText("Editor");
    await app.locator('#flow [data-nav="current"]').click();
    await expect(app.locator("#pageTitle")).toHaveText("Analyze");
    expect(await app.evaluate(() => location.hash)).toBe("");
    const ed = app.locator("#flow [data-flow-editor]");
    await expect(ed).toBeEnabled();                                   // remembers the last clip
    await ed.click();
    await expect.poll(() => app.evaluate(() => location.hash)).toBe("#editor/job-a/c94");
    await app.locator('#flow [data-nav="queue"]').click();
    await expect(app.locator("#rvFilters select").first()).toBeVisible();
    await expect(app.locator("[data-rv-classic]")).toHaveCount(0);   // 7e: every drawer feature has a home in the Editor
  });
});

test.describe("Expired group (162)", () => {
  test.use({ reducedMotion: "reduce" });
  test("clips of an ended campaign leave the grid for a collapsed Expired group", async ({ app, api }) => {
    IME.push(EXPIRED);
    try {
      await open(app, api);
      await expect(app.locator("#rvGrid .rv-clip")).toHaveCount(4);
      const ex = app.locator(".rv-expired");
      await expect(ex.locator("summary")).toHaveText("Expired · 1 clip (campaign ended)");
      await expect(app.locator("#rv-c50")).toBeHidden();
      await ex.locator("summary").click();
      await expect(app.locator("#rv-c50 .rv-earn")).toHaveText("Campaign ended");
    } finally { IME.pop(); }
  });
});
