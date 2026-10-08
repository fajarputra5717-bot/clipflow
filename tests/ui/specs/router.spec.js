// 170/171: the URL is the view (reload / back / forward restore it; a bare URL opens the last view used), and the
// Editor step with no clip open shows "Pick a clip" (compact Review grid, same saved filters) instead of the old list.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const clip = (id, title) => ({ id, job_id: "job-done", status: "review", ai_title: title, job_title: "Mock stream", score: 90,
  updated_at: "2026-10-07T10:00:00+00:00", campaign: null, rule_checks: [] });
async function mockPick(app, api) {
  api.filter = { campaign: "all", job: "all", status: "to_review" };
  await app.route(/\/api\/review\/filter$/, async (route) => {
    if (route.request().method() === "PUT") { api.filter = route.request().postDataJSON(); api.calls.push({ method: "PUT", path: "/api/review/filter", body: api.filter }); }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api.filter) });
  });
  await app.route(/\/api\/review\/clips\?/, (route) => route.fulfill({ status: 200, contentType: "application/json",
    body: JSON.stringify({ header: { kind: "all", title: "All clips", to_review: 2 }, clips: [clip("cand-a", "First clip"), clip("cand-b", "Second clip")] }) }));
}

test("every step writes its hash; reload and back/forward restore the view", async ({ app }) => {
  await app.locator('#flow [data-nav="schedule"]').click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#schedule");
  await expect(app.locator("#scheduleSection")).toBeVisible();
  await app.locator('#flow [data-nav="publish"]').click();
  await expect(app.locator("#publishSection")).toBeVisible();
  await app.goBack();
  await expect(app.locator("#scheduleSection")).toBeVisible();
  await app.goForward();
  await expect(app.locator("#publishSection")).toBeVisible();
  await app.reload();
  await expect(app.locator("#publishSection")).toBeVisible();
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Publish");
});

test("a bare URL opens the last view used", async ({ app }) => {
  await app.locator('#flow [data-nav="schedule"]').click();
  await expect(app.locator("#scheduleSection")).toBeVisible();
  await app.evaluate(() => { history.replaceState(null, "", location.pathname); });
  await app.reload();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#schedule");
  await expect(app.locator("#scheduleSection")).toBeVisible();
});

test("campaign detail has its own hash", async ({ app, api }) => {
  api.campaigns = [{ slug: "ime-roleplay", name: "IME Roleplay", platforms: [], status: { code: "active", label: "Active" }, mine: {} }];
  api.campaignDetail = { "ime-roleplay": { slug: "ime-roleplay", name: "IME Roleplay", status: { code: "active", label: "Active", detail: "" }, mine: {}, view: {} } };
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await app.locator('[data-campaign-card="ime-roleplay"] h3').click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#campaign/ime-roleplay");
  await app.reload();
  await expect(app.locator(".cd-head h2")).toHaveText("IME Roleplay");
  await app.locator("[data-campaign-back]").click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#campaign");
});

test("Editor with no clip = Pick a clip; a card opens #editor/<job>/<clip>; status filter is saved", async ({ app, api }) => {
  await mockPick(app, api);
  await app.locator("#flow [data-flow-editor]").click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#editor");
  await expect(app.locator("#pickSection")).toBeVisible();
  await expect(app.locator("#currentSection")).toBeHidden();
  await expect(app.locator(":text('Tap a job to review'):visible")).toHaveCount(0);
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Editor");
  await expect(app.locator(".pk-card .pk-title")).toHaveText(["First clip", "Second clip"]);
  await app.locator('[data-pick-status="all"]').click();
  await expect.poll(() => api.calls.find((c) => c.path === "/api/review/filter")?.body?.status).toBe("all");
  await expect(app.locator(".pk-card").nth(1)).toHaveAttribute("href", "#editor/job-done/cand-b");
});
