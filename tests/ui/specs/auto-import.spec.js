// P3 part 7 (183): stepper step 2 "Auto-import" = GET /api/auto-import. Source channels per campaign with a watch
// switch (PUT /api/auto-import/watch), recent imports with their state; ended campaigns can't be switched on.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const seed = (api) => {
  api.autoImport = { interval_min: 15, min_minutes: 5,
    campaigns: [
      { slug: "fandra-octo", name: "Fandra Octo", status: "Active", status_code: "active", can_watch: true, channels: [
        { channel: "https://www.youtube.com/@fandraocto", label: "@fandraocto", content: "livestreams of any game", watched: true, line: "checked 4 min ago", error: null, guardrails: { max_per_day: 2, min_minutes: 5, max_minutes: 240, include: [], exclude: [], pause_below_gb: null, telegram_note: true }, guard_text: "Max 2 a day · 5 min–4 h · Telegram note" }] },
      { slug: "old-camp", name: "Old campaign", status: "Ended", status_code: "ended", can_watch: false, channels: [
        { channel: "https://www.youtube.com/@oldchan", label: "@oldchan", content: "", watched: false, line: "not watched", error: null, guardrails: { max_per_day: 2, min_minutes: 5, max_minutes: 240, include: [], exclude: [], pause_below_gb: null, telegram_note: true }, guard_text: "Max 2 a day · 5 min–4 h · Telegram note" }] }],
    imports: [
      { id: "i1", title: "Stream: Minecraft hardcore", url: "https://www.youtube.com/watch?v=a", campaign_name: "Fandra Octo", channel: "@fandraocto",
        duration_fmt: "3:12:40", when_fmt: "12 Oct, 09:12", status: "imported", label: "Ready for review", badge: "attention", job_id: "job-done" },
      { id: "i2", title: "Short teaser", url: "https://www.youtube.com/watch?v=b", campaign_name: "Fandra Octo", channel: "@fandraocto",
        duration_fmt: "0:52", when_fmt: "11 Oct, 21:03", status: "skipped", label: "Skipped · Under 5 min", badge: "cancelled", job_id: null }] };
};

test("Auto-import: switches per source channel, recent imports, ended campaign locked, hash #import", async ({ app, api }) => {
  seed(api);
  await app.locator('#flow [data-nav="import"]').click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#import");
  await expect(app.locator("#importSection")).toBeVisible();
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Auto-import");
  await expect(app.locator("#pageTitle")).toHaveText("Auto-import");
  const on = app.locator('[data-ai-channel="https://www.youtube.com/@fandraocto"]');
  await expect(on).toHaveAttribute("aria-checked", "true");
  await expect(app.locator('[data-ai-channel="https://www.youtube.com/@oldchan"]')).toBeDisabled();
  await expect(app.locator(".ai-imports .badge")).toHaveText(["Ready for review", "Skipped · Under 5 min"]);
  await expect(app.locator('.ai-imports a[href="#review/job-done"]')).toHaveText("Stream: Minecraft hardcore");
  await on.click();
  await expect(on).toHaveAttribute("aria-checked", "false");
  expect(api.calls.filter((c) => c.method === "PUT" && c.path === "/api/auto-import/watch").at(-1).body)
    .toEqual({ campaign: "fandra-octo", channel: "https://www.youtube.com/@fandraocto", enabled: false });
  await expect(app.locator(".ai-camp").first()).toContainText("not watched");
  await expect(app.locator(".ai-camp").first().locator(".ai-guard")).toContainText("Max 2 a day · 5 min–4 h");
  await expect(app.locator(".ai-camp").first().locator("[data-ai-limits]")).toHaveAttribute("href", "#campaign/fandra-octo");
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("Auto-import with no source channels shows the empty state", async ({ app }) => {
  await app.locator('#flow [data-nav="import"]').click();
  await expect(app.locator("#importBody")).toContainText("No campaign lists a source channel yet");
});

test("Campaign page: Auto-import box saves per-channel limits (184)", async ({ app, api }) => {
  seed(api);
  api.campaigns = [{ slug: "fandra-octo", name: "Fandra Octo", platforms: [], status: { code: "active", label: "Active" }, mine: {} }];
  api.campaignDetail = { "fandra-octo": { slug: "fandra-octo", name: "Fandra Octo", status: { code: "active", label: "Active", detail: "" }, mine: {}, view: {} } };
  await app.evaluate(() => { location.hash = "#campaign/fandra-octo"; });
  const box = app.locator("#cdAutoImport");
  await expect(box).toBeVisible();
  await expect(box.locator(".ai-guard")).toHaveText("Max 2 a day · 5 min–4 h · Telegram note");
  await box.locator(".ai-limits > summary").click();
  await box.locator('input[name="max_per_day"]').fill("3");
  await box.locator('input[name="exclude"]').fill("#shorts, reupload");
  await box.locator('input[name="pause_below_gb"]').fill("50");
  await box.locator('input[name="telegram_note"]').uncheck();
  await box.getByRole("button", { name: "Save limits" }).click();
  await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path === "/api/auto-import/watch").length).toBe(1);
  expect(api.calls.find((c) => c.method === "PUT").body).toEqual({ campaign: "fandra-octo", channel: "https://www.youtube.com/@fandraocto",
    guardrails: { max_per_day: "3", min_minutes: "5", max_minutes: "240", include: "", exclude: "#shorts, reupload", pause_below_gb: "50", telegram_note: false } });
  await expect(box.locator(".ai-guard")).toHaveText("Max 3 a day");
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("deploy rule (184): a route the backend doesn't know yet shows 'updating', not the raw 404", async ({ app }) => {
  await app.route(/\/api\/auto-import(\?.*)?$/, (r) => r.fulfill({ status: 404, contentType: "application/json", body: '{"detail":"Not Found"}' }));
  await app.locator('#flow [data-nav="import"]').click();
  await expect(app.locator("#importBody .error-box")).toHaveText("ClipFlow is updating… try again in a minute.");
});

test("Campaign page: 'Found, not imported: confirm?' imports a video on request (187)", async ({ app, api }) => {
  seed(api);
  api.autoImport.imports.push({ id: "i3", title: "Old VOD reupload", url: "https://www.youtube.com/watch?v=c", campaign_name: "Fandra Octo",
    channel: "@fandraocto", duration_fmt: "", when_fmt: "12 Oct, 10:00", status: "skipped", label: "Skipped · No upload time", badge: "cancelled",
    job_id: null, confirmable: true });
  api.campaigns = [{ slug: "fandra-octo", name: "Fandra Octo", platforms: [], status: { code: "active", label: "Active" }, mine: {} }];
  api.campaignDetail = { "fandra-octo": { slug: "fandra-octo", name: "Fandra Octo", status: { code: "active", label: "Active", detail: "" }, mine: {}, view: {} } };
  await app.evaluate(() => { location.hash = "#campaign/fandra-octo"; });
  const list = app.locator("#cdAutoImport .ai-confirm");
  await expect(list.locator("h4")).toHaveText("Found, not imported: confirm?");
  await expect(list.locator(".ai-li")).toHaveCount(1);                    // the "Under 5 min" skip is NOT confirmable
  await expect(list).toContainText("No upload time");
  await list.getByRole("button", { name: "Import anyway" }).click();
  await expect.poll(() => api.calls.filter((c) => c.method === "POST" && c.path === "/api/auto-import/imports/i3/import").length).toBe(1);
  await expect(app.locator("#cdAutoImport .ai-confirm")).toHaveCount(0);
});
