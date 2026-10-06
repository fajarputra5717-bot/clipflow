// Read-only checks against the REAL backend. Off unless CLIPFLOW_UI_LIVE=1; needs CLIPFLOW_API_TOKEN (a cf_… token
// from Account → API tokens; the shared CLIPFLOW_API_KEY was removed in 127).
// Every non-GET /api request is aborted, so nothing can be created, edited or deleted.
const base = require("@playwright/test");
const { nav, blockingProblems } = require("../fixtures");
const { test, expect } = base;

test.skip(!process.env.CLIPFLOW_UI_LIVE, "set CLIPFLOW_UI_LIVE=1 (and CLIPFLOW_API_TOKEN) to run");

test("live app loads, lists jobs and opens one read-only", async ({ page }) => {
  const errors = [], blocked = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => { errors.push("dialog: " + d.message()); d.dismiss(); });
  await page.setExtraHTTPHeaders({ Authorization: "Bearer " + (process.env.CLIPFLOW_API_TOKEN || "") }); // per-user token (P1.5)
  await page.route("**/api/**", (r) => (r.request().method() === "GET" ? r.continue() : (blocked.push(r.request().url()), r.abort())));
  await page.goto("/");
  await page.waitForResponse((r) => r.url().includes("/api/jobs?scope=current") && r.ok());
  expect(await blockingProblems(page, ["#youtubeUrl"])).toEqual([]);
  await nav(page, "queue");
  const first = page.locator("[data-queue-open]").first();
  if (await first.count()) {
    await first.click();
    await expect(page.locator("#queueDetail")).toBeVisible();
    const edit = page.locator("#queueDetail [data-edit]").first();
    if (await edit.count()) { await edit.click(); await expect(edit).toHaveAttribute("aria-expanded", "true"); await edit.click(); }
  }
  expect(errors).toEqual([]);
  expect(blocked, "live mode must not write").toEqual([]);
});
