// P3 parts 1–3 (157–159): stepper step 1 "Campaign" = one card per visible campaign: status badge + detail (week /
// days left), payout sentence, platforms, my posted/claimed/paid, budget text, my monthly-cap meter. Money and
// status come formatted from the API (payouts.describe, campaign_status); the UI only places them.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const camp = (o) => ({ slug: "ime-roleplay", name: "IME Roleplay X Motion Klip", brief_pending: false, platforms: ["tiktok", "instagram", "youtube"],
  default_layout: "none", sources: [], hashtags: ["#ime"], visibility: "shared", paused: false, can_edit: true, created_by_me: true,
  status: { code: "active", label: "Active", detail: "Week 1 · 1 day left", last_day: "2026-10-28", days_left: 22 },
  week: { id: "W1", days_left: 1 }, payout_text: "Rp 200.000 per post at 40.000 views, max 2 per platform account/month",
  budget_text: "Rp 20.000.000/month (4 refills of Rp 5.000.000)",
  cap_meter: { label: "Your month: Rp 400.000 of Rp 2.400.000 cap", fraction: 0.1667 },
  mine: { posted: 3, claimed: 2, paid: 1, planned: 1, paid_fmt: "Rp 200.000", expected_fmt: "Rp 200.000" }, ...o });

test("campaign cards: status, payout line, my totals, budget + cap meter, ended last", async ({ app, api }) => {
  api.campaigns = [
    camp({ slug: "old", name: "Old campaign", status: { code: "ended", label: "Ended", detail: "Ended 28 Sep" }, budget_text: null, cap_meter: null,
      payout_text: "Payout not set yet", mine: { posted: 0, claimed: 0, paid: 0, paid_fmt: "Rp 0" } }),
    camp(),
    camp({ slug: "fandra-octo", name: "Fandra Octo", status: { code: "ending_soon", label: "Ending soon", detail: "3 days left" }, budget_text: null,
      cap_meter: null, payout_text: "Rp 12.000 per full 3.000 views, max Rp 1.992.000" }),
  ];
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await expect(app.locator("#campaignSection")).toBeVisible();
  await expect(app.locator("#pageTitle")).toHaveText("Campaign");
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Campaign");
  await expect(app.locator(".camp-card h3")).toHaveText(["IME Roleplay X Motion Klip", "Fandra Octo", "Old campaign"]);
  const ime = app.locator('[data-campaign-card="ime-roleplay"]');
  await expect(ime.locator(".badge")).toHaveText("Active");
  await expect(ime.locator(".badge")).toHaveClass(/completed/);
  await expect(ime.locator(".camp-detail")).toHaveText("Week 1 · 1 day left");
  await expect(ime.locator(".camp-pay")).toHaveText("Rp 200.000 per post at 40.000 views, max 2 per platform account/month");
  await expect(ime.locator(".camp-kv")).toHaveText(/3 posted\s*2 claimed\s*Rp 200.000 paid\s*1 planned/);
  await expect(ime.locator(".camp-meter-label").last()).toHaveText("Your month: Rp 400.000 of Rp 2.400.000 cap");
  await expect(ime.locator('[role="meter"]')).toHaveAttribute("aria-valuenow", "17");
  await expect(app.locator('[data-campaign-card="fandra-octo"] .badge')).toHaveClass(/attention/);
  await expect(app.locator('[data-campaign-card="old"]')).toHaveClass(/is-ended/);
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await app.screenshot({ path: `test-results/campaign-cards-${test.info().project.name}.png`, fullPage: true });
});

test("paused campaign is disabled in the Analyze form", async ({ app, api }) => {
  api.campaigns = [camp({ paused: true, status: { code: "paused", label: "Paused", detail: "" } }), camp({ slug: "fandra-octo", name: "Fandra Octo" })];
  await app.reload();
  await expect(app.locator('#jobCampaign option[value="ime-roleplay"]')).toBeDisabled();
  await expect(app.locator('#jobCampaign option[value="ime-roleplay"]')).toHaveText("IME Roleplay X Motion Klip (paused)");
  await expect(app.locator('#jobCampaign option[value="fandra-octo"]')).toBeEnabled();
});
