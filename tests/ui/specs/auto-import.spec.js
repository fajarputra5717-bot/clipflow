// P3 part 7 (183): stepper step 2 "Auto-import" = GET /api/auto-import. Source channels per campaign with a watch
// switch (PUT /api/auto-import/watch), recent imports with their state; ended campaigns can't be switched on.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const seed = (api) => {
  api.autoImport = { interval_min: 15, min_minutes: 5,
    campaigns: [
      { slug: "fandra-octo", name: "Fandra Octo", status: "Active", status_code: "active", can_watch: true, channels: [
        { channel: "https://www.youtube.com/@fandraocto", label: "@fandraocto", content: "livestreams of any game", watched: true, line: "checked 4 min ago", error: null }] },
      { slug: "old-camp", name: "Old campaign", status: "Ended", status_code: "ended", can_watch: false, channels: [
        { channel: "https://www.youtube.com/@oldchan", label: "@oldchan", content: "", watched: false, line: "not watched", error: null }] }],
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
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("Auto-import with no source channels shows the empty state", async ({ app }) => {
  await app.locator('#flow [data-nav="import"]').click();
  await expect(app.locator("#importBody")).toContainText("No campaign lists a source channel yet");
});
