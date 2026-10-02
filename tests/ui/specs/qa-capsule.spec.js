// QA (Lane C) P0 gate: row progress must be an island-style capsule (097), no separate bar design.
const { test, expect, job } = require("../fixtures");
test("job card progress is a mini-island capsule, no bar", async ({ app, api }, info) => {
  api.current = [job({ id: "job-run", status: "rendering", progress: 45, source_title: "Capsule check" })];
  const card = app.locator('#currentJobs [data-job-id="job-run"]');
  await expect(card).toBeVisible({ timeout: 8_000 });
  const cap = card.locator(".mini-island");
  await expect(cap).toBeVisible();
  const stray = await card.evaluate((n) => [...n.querySelectorAll(".mini-bar, .mini-bar-track, .progress-ring, progress, [role=progressbar]")]
    .filter((e) => !e.closest(".mini-island")).map((e) => e.tagName + "." + e.className + " in " + (e.parentElement && e.parentElement.className)));
  console.log("stray progress outside capsule:", JSON.stringify(stray));
  expect(stray).toEqual([]);
  const s = await cap.evaluate((n) => { const c = getComputedStyle(n); return { bg: c.backgroundColor, radius: c.borderRadius, h: c.height }; });
  const isl = await app.locator("#island").evaluate((n) => getComputedStyle(n).backgroundColor);
  console.log("capsule", JSON.stringify(s), "island bg", isl);
  expect(parseFloat(s.radius)).toBeGreaterThanOrEqual(parseFloat(s.h) / 2 - 1); // pill shape
  await card.screenshot({ path: `test-results/capsule-${info.project.name}.png` });
});
