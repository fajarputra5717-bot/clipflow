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
