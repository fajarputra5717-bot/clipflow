// UI phase 2, Campaigns (owner 2026-10-14): "New campaign" in the title row; the whole card opens the campaign (mouse +
// keyboard); a deadline ≤ 2 days is highlighted; "Payout not set yet" = a Set payout action that opens a payout form
// (PUT rules.payout); the budget / cap bar is on every card.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });
const SHOTS = process.env.P2_SHOTS;

const camp = (o) => ({ slug: "ime-roleplay", name: "IME Roleplay X Motion Klip", platforms: ["tiktok"], visibility: "shared", paused: false, can_edit: true,
  status: { code: "active", label: "Active", detail: "Week 2 · 6 days left", days_left: 20 }, week: { id: "W2", days_left: 6 },
  payout_text: "Rp 200.000 per post at 40.000 views", budget_text: "Rp 20.000.000/month",
  cap_meter: { label: "Your month: Rp 400.000 of Rp 2.400.000 cap", fraction: 0.17 }, mine: { posted: 3, claimed: 2, paid_fmt: "Rp 200.000" }, ...o });
const cards = [camp(),
  camp({ slug: "fandra", name: "Fandra Octo", status: { code: "ending_soon", label: "Ending soon", detail: "2 days left", days_left: 2 }, week: null, cap_meter: null, budget_text: null }),
  camp({ slug: "new-brand", name: "New brand", payout_text: "Payout not set yet", cap_meter: null, week: null })];

async function open(app, api, list = cards) {
  api.campaigns = list;
  api.campaignDetail = { "new-brand": { ...list[list.length - 1], rules: { platforms: ["tiktok"], hashtags: ["#x"], payout: { stated_as: "?" } },
    view: { payout: [], platforms: [], hashtags: [], weeks: [] }, brief_text: "" } };
  await app.reload();
  await app.locator('#flow [data-nav="campaign"]').click();
  await expect(app.locator(".camp-card")).toHaveCount(list.length);
}

test("New campaign sits in the title row (admins)", async ({ app, api }) => {
  await open(app, api);
  const btn = app.locator("#campaignActions [data-campaign-new]");
  await expect(btn).toBeVisible();
  const [b, h] = [await btn.boundingBox(), await app.locator("#campaignTitle").boundingBox()];
  expect(Math.abs((b.y + b.height / 2) - (h.y + h.height / 2))).toBeLessThan(40);   // same row as the heading
  await expect(app.locator(".cn-bar")).toHaveCount(0);
  if (SHOTS) await app.screenshot({ path: `${SHOTS}/campaigns-${test.info().project.name}.png` });
});

test("the whole card opens the campaign, by click anywhere and by keyboard", async ({ app, api }) => {
  await open(app, api);
  await expect(app.locator(".camp-open")).toHaveCount(0);                        // no Details button
  const card = app.locator('[data-campaign-card="fandra"]'), box = await card.boundingBox();
  await app.mouse.click(box.x + box.width - 20, box.y + box.height - 12);        // a corner, away from the title
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#campaign/fandra");
  await app.locator('#flow [data-nav="campaign"]').click();
  await app.locator('[data-campaign-card="ime-roleplay"] .camp-link').focus();
  await app.keyboard.press("Enter");
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#campaign/ime-roleplay");
});

test("deadline ≤ 2 days is highlighted; budget bar on every card", async ({ app, api }) => {
  await open(app, api);
  await expect(app.locator('[data-campaign-card="fandra"]')).toHaveClass(/is-due/);
  await expect(app.locator('[data-campaign-card="fandra"] .camp-due')).toHaveText("Ends in 2 days");
  await expect(app.locator('[data-campaign-card="ime-roleplay"]')).not.toHaveClass(/is-due/);
  for (const slug of ["ime-roleplay", "fandra", "new-brand"]) await expect(app.locator(`[data-campaign-card="${slug}"] [role=meter]`)).toHaveCount(1);
  await expect(app.locator('[data-campaign-card="fandra"] .camp-meter-label')).toHaveText("No cap set");
  await expect(app.locator('[data-campaign-card="new-brand"] .camp-meter-label')).toHaveText("Budget Rp 20.000.000/month · no cap set");
});

test("Payout not set yet → Set payout → form → PUT rules.payout", async ({ app, api }) => {
  await open(app, api);
  const set = app.locator('[data-campaign-card="new-brand"] [data-campaign-payout]');
  await expect(set).toHaveText("Set payout");
  await set.click();
  await expect.poll(() => app.evaluate(() => location.hash)).toBe("#campaign/new-brand");
  const form = app.locator("[data-cd-payout]");
  await expect(form).toBeVisible();
  await expect(app.locator("#campaignActions [data-campaign-new]")).toHaveCount(0);   // only on the list
  const kinds = await form.locator("[data-cd-paykind]").evaluateAll((b) => new Set(b.map((x) => Math.round(x.getBoundingClientRect().top))).size);
  expect(kinds).toBe(1);                                                          // the three kinds fit one row
  if (SHOTS) await app.screenshot({ path: `${SHOTS}/campaign-payout-${test.info().project.name}.png` });
  await form.locator("[data-cd-paykind=block]").click();
  await expect(app.locator("[data-cd-paykind=block]")).toHaveAttribute("aria-pressed", "true");
  await app.locator("[data-cd-payout] input[name=amount]").fill("12.000");
  await app.locator("[data-cd-payout] button[type=submit]").click();
  await expect(app.locator("[data-cd-payout] .account-msg")).toHaveText("Enter the number of views (a whole number).");
  await app.locator("[data-cd-payout] input[name=views]").fill("3000");
  await app.locator("[data-cd-payout] input[name=max]").fill("500000");
  await app.locator("[data-cd-payout] button[type=submit]").click();
  await expect.poll(() => api.calls.find((c) => c.method === "PUT" && c.path === "/api/campaigns/new-brand")?.body?.rules?.payout)
    .toEqual({ currency: "IDR", model: "per_block", per_block: 12000, block_views: 3000, max_paid_views_per_video: 500000 });
  const rules = api.calls.find((c) => c.method === "PUT").body.rules;
  expect(rules.hashtags).toEqual(["#x"]);                                         // the rest of the rules is kept
});

test("members see Payout not set yet as text, no action", async ({ app, api }) => {
  await open(app, api, cards.map((c) => ({ ...c, can_edit: false })));
  await expect(app.locator('[data-campaign-card="new-brand"] [data-campaign-payout]')).toHaveCount(0);
  await expect(app.locator('[data-campaign-card="new-brand"]')).toContainText("Payout not set yet");
});
