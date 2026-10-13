// Deep audit M4: layout shift stays under 0.05 on first paint and on the Import → Review switch, with a 300 ms API
// delay (data arrives after the first frame, like the real server). Was 0.083 (768) / 0.061 (1280) on first paint
// (late "Detected from the audio." / "Your default: N" notes) and 0.084 (390) on the switch (Review's loading line
// pushed down by the filters).
const { test, expect, job, reviewClip } = require("../fixtures");

const OBS = () => { window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: "layout-shift", buffered: true }); };
const slow = (app) => app.route("**/api/**", async (r) => { await new Promise((ok) => setTimeout(ok, 300)); return r.fallback(); });

test.describe("layout shift", () => {
  for (const w of [390, 768, 1280]) {
    test(`first paint at ${w} px < 0.05`, async ({ app, api }) => {
      test.skip(test.info().project.name !== "desktop", "viewport set per case");
      api.current = [job({ id: "j1", status: "review", source_title: "A stream" })];
      api.jobs = { ...api.jobs, j1: api.current[0] };
      await app.setViewportSize({ width: w, height: 900 });
      await slow(app);
      await app.addInitScript(OBS);
      await app.evaluate(() => { location.hash = ""; });
      await app.reload(); await app.waitForTimeout(2000);
      expect(await app.evaluate(() => window.__cls)).toBeLessThan(0.05);
    });
  }
  for (const w of [390, 768]) {
    test(`Import → Review at ${w} px < 0.05`, async ({ app, api }) => {
      test.skip(test.info().project.name !== "desktop", "viewport set per case");
      api.current = [job({ id: "j1", status: "review", source_title: "A stream" })];
      api.jobs = { ...api.jobs, j1: api.current[0] };
      await app.setViewportSize({ width: w, height: 844 });
      const f = (body) => async (route) => { await new Promise((ok) => setTimeout(ok, 300)); route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }); };
      await slow(app);
      await app.route(/\/api\/review\/filter$/, f({ campaign: "all", job: "all", status: "to_review" }));
      await app.route(/\/api\/review\/clips\?/, f({ header: { kind: "all", title: "All clips", to_review: 3 }, clips: [1, 2, 3].map((i) => reviewClip({ id: "c" + i, score: 90 - i })) }));
      await app.addInitScript(OBS);
      await app.evaluate(() => { location.hash = "#import"; }); await app.reload(); await app.waitForTimeout(1500);
      await app.evaluate(() => { window.__cls = 0; location.hash = "#review"; });
      await expect(app.locator("#rvFilters select").first()).toBeVisible();
      await app.waitForTimeout(1200);
      expect(await app.evaluate(() => window.__cls)).toBeLessThan(0.05);
    });
  }
});
