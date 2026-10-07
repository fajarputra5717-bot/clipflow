// QA lane C: gate-P2 UI write checks on STAGING only (144 panel + send to phone, 145 posting times, cross-user).
const { test, expect } = require("@playwright/test");
const U = require(process.env.QA_USERS), B = "http://127.0.0.1:8080";
if (!/^http:\/\/(127\.0\.0\.1|localhost):8080$/.test(B)) throw new Error("REFUSES non-staging");
const CID = process.env.QA_CID;                       // lane-c-b Fandra final
test.describe.configure({ mode: "serial" });
async function login(page, u) {
  const r = await page.request.post(B + "/api/auth/login", { data: { username: u, password: U[u].pw } });
  expect(r.status()).toBeLessThan(300);
}
const log = (...a) => console.log("QA", ...a);
test("panel: mark posted → views → claimed → paid; send to phone; posting times; cross-user", async ({ page, browser }, info) => {
  test.skip(info.project.name !== "desktop", "writes once (desktop)");
  await login(page, "lane-c-b");
  const accts = await (await page.request.get(B + "/api/accounts")).json();
  const list = accts.accounts || accts;
  if (!list.some((a) => a.platform === "instagram" && a.handle === "lane_c_b_ig"))
    expect((await page.request.post(B + "/api/accounts", { data: { platform: "instagram", handle: "@lane_c_b_ig" } })).status()).toBe(200);
  await page.goto(B + "/"); await page.locator('#flow [data-nav="publish"]').click();
  const card = page.locator(`[data-publish-card="${CID}"]`); await expect(card).toBeVisible({ timeout: 15000 });
  await card.locator(`[data-chip="${CID}:instagram"]`).click();
  await page.locator(`[data-mark-open="${CID}:instagram"]`).click();
  await page.locator(`[data-mark-form="${CID}:instagram"] input[type=url]`).fill("https://www.instagram.com/reel/laneCb144ui/");
  await page.locator(`[data-mark-form="${CID}:instagram"] button[type=submit]`).click();
  await expect(card.locator(`[data-chip="${CID}:instagram"]`)).toContainText(/Posted/, { timeout: 8000 });
  log("posted chip", (await card.locator(`[data-chip="${CID}:instagram"]`).innerText()).replace(/\s+/g, " "));
  const vf = page.locator("[data-views-form]").first(); await vf.locator("input").fill("41000"); await vf.locator("button[type=submit]").click();
  await expect(card.locator(`[data-chip="${CID}:instagram"]`)).toContainText("41.000", { timeout: 8000 });
  await page.locator("[data-claim-open]", { hasText: "Mark claimed" }).click();
  await page.locator("[data-claim-form] button[type=submit]").click();
  await expect(card.locator(`[data-chip="${CID}:instagram"]`)).toContainText(/Claimed/, { timeout: 8000 });
  await page.locator("[data-claim-open]", { hasText: "Mark paid" }).click();
  await page.locator("[data-paid-form] button[type=submit]").click();
  await expect(card.locator(`[data-chip="${CID}:instagram"]`)).toContainText(/Paid/, { timeout: 8000 });
  const posts = await (await page.request.get(B + "/api/posts")).json();
  const p = (posts.posts || posts).find((x) => x.candidate_id === CID && x.platform === "instagram");
  log("post", JSON.stringify({ id: p.id, status: p.status, views: p.views, claimed_views: p.claimed_views, paid_rp: p.paid_rp, eligible: p.eligible }));
  await page.locator(`[data-send-phone="${CID}"]`).click();
  await expect(page.locator(`[data-send-phone="${CID}"]`)).toBeDisabled();
  // posting times (145): add 18:30 to TikTok, save
  await page.locator('[data-nav="settings"]').first().click();
  await page.locator('[data-ptime-input="tiktok"]').fill("18:30"); await page.locator('[data-ptime-add="tiktok"]').click();
  await page.locator("#postingTimesSave").click(); await expect(page.locator("#postingTimes")).toContainText("Saved.");
  await page.screenshot({ path: `${process.env.QA_SHOTS}/p2ui-postingtimes.png` });
  const st = await (await page.request.get(B + "/api/settings")).json();
  log("B POSTING_TIMES", JSON.stringify(st.POSTING_TIMES || st.settings?.POSTING_TIMES));
  // cross-user: lane-c-a must not see or touch B's post, and keeps its own posting times
  const ctxA = await browser.newContext(); const pa = await ctxA.newPage(); await login(pa, "lane-c-a");
  for (const [m, body] of [["get"], ["patch", { views: 1 }], ["delete"]])
    log(`A ${m} B's post`, (await pa.request[m](B + `/api/posts/${p.id}`, body ? { data: body } : {})).status());
  log("A send-to-phone B's clip", (await pa.request.post(B + "/api/publish/send-to-phone", { data: { candidate_id: CID } })).status());
  log("A mark post on B's clip", (await pa.request.post(B + "/api/posts", { data: { candidate_id: CID, platform: "tiktok", status: "planned" } })).status());
  const sa = await (await pa.request.get(B + "/api/settings")).json();
  log("A POSTING_TIMES", JSON.stringify(sa.POSTING_TIMES || sa.settings?.POSTING_TIMES));
  log("A queue has B's clip", JSON.stringify(await (await pa.request.get(B + "/api/publish-queue")).json()).includes(CID));
});
