// P3 part 4 (166): New campaign = paste brief → parse (island task, no spinner) → form pre-filled, unsure fields
// highlighted; Save stays disabled until every unsure field is confirmed; the brief is sent verbatim. Admin only.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const parsed = () => ({ name: "Fandra Octo", slug: "fandra-octo-2", ai_derived: ["platforms"], ai_reasons: ["platforms not recognised"],
  rules: { name: "Fandra Octo", platforms: ["tiktok"], hashtags: { required_in_order: ["#fandra", "#octo"] },
    payout: { currency: "IDR", model: "per full view block", block_views: 3000, block_rp: 12000 } },
  unsure: [{ field: "platforms", why: "AI-derived from the brief: confirm in the Campaign screen", source: "ai" },
    { field: "weeks.year", why: "brief gives day + month only" }],
  payout_text: "Rp 12.000 per full 3.000 views", view: { payout: ["Rp 12.000 per full 3.000 views"], weeks: [], content_rules: ["No reuploads"] } });

test("admin: brief → form, unsure highlighted, confirm all before Save, saved campaign opens", async ({ app, api }) => {
  api.campaigns = [];
  api.parsedBrief = parsed();
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await app.locator("[data-campaign-new]").click();
  await app.locator("[data-cn-parse]").click();
  await expect(app.locator("#cnMsg")).toHaveText("Paste the brief first.");
  await app.locator("#cnBrief").fill("BRIEF Fandra\n#fandra #octo");
  await app.locator("[data-cn-parse]").click();
  await expect(app.locator("#cnName")).toHaveValue("Fandra Octo");
  await expect(app.locator("#cnSlug")).toHaveValue("fandra-octo-2");
  await expect(app.locator("#cnTags")).toHaveValue("#fandra\n#octo");
  await expect(app.locator('[data-cn-plat="tiktok"]')).toHaveAttribute("aria-pressed", "true");
  await expect(app.locator(".cn-field.is-unsure")).toHaveCount(1);              // platforms (AI) highlighted
  await expect(app.locator(".cn-unsure .badge")).toHaveText(["AI"]);
  await expect(app.locator("#cnPreview")).toContainText("No reuploads");
  const save = app.locator("[data-cn-save]");
  await expect(save).toBeDisabled();
  await app.locator('[data-cn-plat="youtube"]').click();
  await app.locator('[data-cn-confirm="platforms"]').check();
  await expect(save).toBeDisabled();
  await app.locator('[data-cn-confirm="weeks.year"]').check();
  await expect(save).toBeEnabled();
  await app.locator("[data-cn-preview]").click();
  await expect(app.locator("#cnPreview")).toContainText("Preview: youtube,tiktok");
  await app.locator('[data-cn-vis="private"]').click();
  await save.click();
  await expect(app.locator(".cd-head h2")).toHaveText("Fandra Octo");
  const b = api.createdCampaign;
  expect(b).toMatchObject({ slug: "fandra-octo-2", name: "Fandra Octo", visibility: "private", brief_text: "BRIEF Fandra\n#fandra #octo",
    confirmed: ["platforms", "weeks.year"] });
  expect(b.rules.platforms).toEqual(["youtube", "tiktok"]);
  expect(b.rules.hashtags.required_in_order).toEqual(["#fandra", "#octo"]);
  expect(b.rules.payout.block_rp).toBe(12000);
});

test("members get no New campaign button", async ({ app, api }) => {
  api.campaigns = [];
  api.user = { id: "u-1", username: "m", role: "member" };
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await expect(app.locator("#campaignList")).toContainText("No campaigns yet.");
  await expect(app.locator("[data-campaign-new]")).toHaveCount(0);
});
