// P3 part 8 (181): stepper step 8 "Track" = GET /api/track (shared/track.py). Tiles, by campaign / by platform,
// top clips by views with the amount state; every amount comes formatted from the server (payouts).
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const row = (name, posts, views, exp, paid) => ({ key: name, name, posts, views_fmt: views, expected_fmt: exp, paid_fmt: paid });
test("Track: tiles, breakdowns, top clips (USD shown with IDR), hash #track", async ({ app, api }) => {
  api.track = { tiles: { posts: 4, views_fmt: "110.000", paid_fmt: "Rp 200.000", expected_fmt: "Rp 424.000", claimed: 2, paid: 1, at_cap: 1 },
    campaigns: [row("IME Roleplay", 3, "103.000", "Rp 400.000", "Rp 200.000"), row("USD CPM", 1, "7.000", "Rp 24.000", "Rp 0")],
    platforms: [row("TikTok", 3, "103.000", "Rp 400.000", "Rp 200.000")],
    top: [{ post_id: "p3", title: "Lompatan GILA", platform: "tiktok", platform_name: "TikTok", campaign_name: "IME Roleplay", views_fmt: "50.000",
            amount_fmt: "Rp 200.000", amount_state: "paid", at_cap: false },
          { post_id: "p1", title: "Second", platform: "youtube", platform_name: "YouTube Shorts", campaign_name: "USD CPM", views_fmt: "10.000",
            amount_fmt: "$15.00 (~Rp 247.500)", amount_state: "estimate", at_cap: true }],
    skipped_currencies: [] };
  await app.locator('#flow [data-nav="track"]').click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#track");
  await expect(app.locator("#trackSection")).toBeVisible();
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Track");
  await expect(app.locator(".tr-tile .tr-v")).toHaveText(["110.000", "Rp 200.000", "Rp 424.000", "2 / 1", "1"]);
  await expect(app.locator(".tr-box").first().locator(".tr-row:not(.tr-head) .tr-name")).toHaveText(["IME Roleplay", "USD CPM"]);
  await expect(app.locator(".tr-top li").nth(1).locator(".tr-amt")).toContainText("$15.00 (~Rp 247.500)");
  await expect(app.locator(".tr-top li").nth(1)).toContainText("At cap");
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("Track with nothing posted shows the empty state", async ({ app }) => {
  await app.locator('#flow [data-nav="track"]').click();
  await expect(app.locator("#trackBody")).toContainText("Nothing posted yet");
});

// UI phase 2, Track (owner 2026-10-14): table headers line up with their columns (names left, numbers right, one
// set of columns for header + rows); a views-per-day line chart for the last 30 days (GET /api/track .daily).
test("Track phase 2: aligned table columns and the 30-day views chart", async ({ app, api }) => {
  const row = (name, posts, views, exp, paid) => ({ key: name, name, posts, views_fmt: views, expected_fmt: exp, paid_fmt: paid });
  const days = Array.from({ length: 30 }, (_, i) => ({ date: `2026-09-${String(15 + i).padStart(2, "0")}`.replace("2026-09-31", "2026-10-01"), views: i * 100, views_fmt: String(i * 100) }));
  api.track = { tiles: { posts: 4, views_fmt: "110.000", paid_fmt: "Rp 200.000", expected_fmt: "Rp 424.000", claimed: 2, paid: 1, at_cap: 1 },
    campaigns: [row("IME Roleplay", 3, "103.000", "Rp 400.000", "Rp 200.000"), row("USD CPM", 1, "7.000", "Rp 24.000", "Rp 0")],
    platforms: [row("TikTok", 3, "103.000", "Rp 400.000", "Rp 200.000")], top: [], skipped_currencies: [],
    daily: { days, total: 43500, total_fmt: "43.500", max: 2900 } };
  await app.locator('#flow [data-nav="track"]').click();
  const table = app.locator(".tr-table").first();
  const cols = await table.evaluate((t) => [...t.querySelectorAll(".tr-row")].map((r) => [...r.children].map((c) => {
    const b = c.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right)]; })));
  const phone = test.info().project.name === "mobile", off = phone ? 1 : 0;     // phones: the name is its own line (header hidden)
  for (const r of cols.slice(1)) r.slice(off).forEach(([l, rt], i) => { expect(Math.abs(rt - cols[0][i + off][1]), `col ${i + off} right edge`).toBeLessThanOrEqual(1); });
  if (!phone) expect(Math.abs(cols[1][0][0] - cols[0][0][0])).toBeLessThanOrEqual(1);   // the name column starts with its header
  await expect(table.locator(".tr-row:not(.tr-head) .tr-name").first()).toHaveText("IME Roleplay");
  expect(await table.locator(".tr-row:not(.tr-head) .tr-name").first().evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBe(true);   // never cut
  expect(await table.locator(".tr-head span").first().evaluate((e) => getComputedStyle(e).textAlign)).not.toBe("right");
  const chart = app.locator(".tr-chart svg");
  await expect(chart).toHaveAttribute("role", "img");
  await expect(chart).toHaveAttribute("aria-label", /Views per day, last 30 days: 43.500 in total, most on/);
  expect(await app.locator(".tr-chart polyline").evaluate((e) => e.getAttribute("points").split(" ").length)).toBe(30);
  await expect(app.locator(".tr-chart .tc-head")).toContainText("43.500");
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (process.env.P2_SHOTS) await app.screenshot({ path: `${process.env.P2_SHOTS}/track-${test.info().project.name}.png`, fullPage: true });
});
