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

// P3 part 5 (161): campaign detail page: sections from GET /api/campaigns/{slug} .view (shared/campaign_view.py).
const detail = (o) => ({ ...camp({ status: { code: "active", label: "Active", detail: "Week 2 · 7 days left" } }), brief_text: "IME Roleplay X Motion Klip\nBayaran Rp 200.000 per video…", rules: {},
  view: { status: { code: "active", label: "Active", detail: "Week 2 · 7 days left" }, period: null,
    payout: ["Rp 200.000 per post at 40.000 views, max 2 per platform account/month", "Claim inside the week the clip was posted."],
    platforms: [{ slug: "tiktok", name: "TikTok" }, { slug: "youtube", name: "YouTube Shorts" }],
    hashtags: ["#imeroleplay", "#imestrong", "#motionklip"], watermark: { required: true, name: "Motion Klip", has_asset: true },
    weeks: [{ id: "W1", dates: "1–7 Oct", state: "closed" }, { id: "W2", dates: "8–14 Oct", state: "open", days_left: 7 }, { id: "W3", dates: "15–21 Oct", state: "upcoming" }],
    content_rules: ["No SARA", "No misleading context"], manual: ["Discord server tag \"MKLP\" required to claim"],
    questions: { open: [{ topic: "Weekly carry over", text: "does unused weekly budget carry over? (unanswered)" }],
      answered: [{ topic: "Uploads oct 29 31", text: "not eligible", date: "2026-10-02" }] },
    claim: { form: "https://forms.gle/x", requires: "Discord tag" }, budget: ["Rp 20.000.000 per month."] }, ...o });

test("campaign detail: payout, my numbers, weeks (open highlighted), hashtags in order, watermark, questions, brief; admin pause", async ({ app, api }) => {
  api.campaigns = [camp()];
  api.campaignDetail = { "ime-roleplay": detail() };
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await app.locator('[data-campaign-card="ime-roleplay"] h3').click();
  await expect(app.locator(".cd-head h2")).toHaveText("IME Roleplay X Motion Klip");
  await expect(app.locator(".cd-sub")).toHaveText("Week 2 · 7 days left");
  await expect(app.locator(".cd-pay li").first()).toHaveText("Rp 200.000 per post at 40.000 views, max 2 per platform account/month");
  await expect(app.locator(".cd-week.is-open")).toContainText("W2 8–14 Oct · 7 days left");
  await expect(app.locator(".cd-week.is-closed")).toContainText("W1");
  await expect(app.locator(".cd-chip", { hasText: "#" })).toHaveText(["1#imeroleplay", "2#imestrong", "3#motionklip"]);
  await expect(app.locator(".cd-wm img")).toHaveAttribute("src", /\/api\/campaigns\/ime-roleplay\/watermark/);
  await expect(app.locator(".cd-q .is-open dt")).toHaveText("Weekly carry over");
  await expect(app.locator(".cd-q dd").first()).toContainText("not eligible (admin, 2026-10-02)");
  await expect(app.locator(".cd-box a", { hasText: "claim form" })).toHaveAttribute("href", "https://forms.gle/x");
  await app.locator(".cd-brief summary").click();
  await expect(app.locator(".cd-brief pre")).toContainText("Bayaran Rp 200.000");
  await app.click("[data-campaign-pause]");
  await expect(app.locator(".cd-head .badge")).toHaveText("Paused");
  expect(api.calls.filter((c) => c.method === "PUT" && c.path === "/api/campaigns/ime-roleplay").at(-1).body).toEqual({ paused: true });
  await expect(app.locator("[data-campaign-pause]")).toHaveText("Resume");
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await app.screenshot({ path: `test-results/campaign-detail-${test.info().project.name}.png`, fullPage: true });
  await app.click("[data-campaign-back]");
  await expect(app.locator(".camp-card")).toHaveCount(1);
});

test("campaign detail: members see no Pause; unknown campaign shows the error with Back", async ({ app, api }) => {
  api.campaigns = [camp({ can_edit: false }), camp({ slug: "gone", name: "Gone" })];
  api.campaignDetail = { "ime-roleplay": detail({ can_edit: false }) };
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await app.locator('[data-campaign-open="ime-roleplay"]').click();
  await expect(app.locator(".cd-head h2")).toBeVisible();
  await expect(app.locator("[data-campaign-pause]")).toHaveCount(0);
  await app.locator('#flow [data-nav="campaign"]').click();          // stepper Campaign = back to the cards
  await expect(app.locator(".camp-card")).toHaveCount(2);
  await app.locator('[data-campaign-open="gone"]').click();
  await expect(app.locator("#campaignList .error-box")).toContainText("Campaign not found");
});
