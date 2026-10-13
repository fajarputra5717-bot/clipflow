// Deep audit M5: Publish, Schedule and Track say "Couldn't load …" + Retry (like Review/Editor), never just the raw
// server detail; Retry reloads the page's data.
const { test, expect } = require("../fixtures");

const PAGES = [
  ["publish", /\/api\/publish-queue/, (a) => a.evaluate(() => window.showTab("publish")), "#publishList", "Couldn't load the publish list."],
  ["schedule", /\/api\/schedule(\?|$)/, (a) => a.evaluate(() => window.showTab("schedule")), "#scheduleList", "Couldn't load the schedule."],
  ["track", /\/api\/track(\?|$)/, (a) => a.evaluate(() => { location.hash = "#track"; }), "#trackBody", "Couldn't load your numbers."],
];

for (const [name, url, go, box, lead] of PAGES) {
  test(`audit M5: ${name} load failure shows a plain lead + Retry, and Retry recovers`, async ({ app }) => {
    let fail = true;
    await app.route(url, (route) => fail
      ? route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) })
      : route.fallback());
    await go(app);
    const err = app.locator(`${box} .load-error`);
    await expect(err).toBeVisible();
    await expect(err.locator("b")).toHaveText(lead);
    await expect(err.locator(".load-error-detail")).toHaveText("boom");          // detail only as small print
    await expect(err).toHaveAttribute("role", "alert");
    fail = false;
    await err.locator("[data-retry-load]").click();
    await expect(app.locator(`${box} .load-error`)).toHaveCount(0);
  });
}

test("audit M6: a read that hits a deploy (502/503) is retried quietly and loads; a write is never resent", async ({ app, api }) => {
  let n = 0;
  await app.route(/\/api\/publish-queue/, (route) => (++n <= 2
    ? route.fulfill({ status: n === 1 ? 502 : 503, contentType: "application/json", body: '{"detail":"ClipFlow is updating… try again in a minute."}' })
    : route.fallback()));
  await app.evaluate(() => window.showTab("publish"));
  await expect.poll(() => n, { timeout: 8_000 }).toBeGreaterThanOrEqual(3);
  await expect(app.locator("#publishList .load-error")).toHaveCount(0);
  let posts = 0;
  await app.route(/\/api\/accounts$/, (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    posts++; return route.fulfill({ status: 502, contentType: "application/json", body: "{}" });
  });
  const res = await app.evaluate(() => window.api("/api/accounts", { method: "POST", body: "{}" }).then(() => "ok", (e) => e.message));
  expect(res).toBe("ClipFlow is updating… try again in a minute.");
  expect(posts).toBe(1);
});
