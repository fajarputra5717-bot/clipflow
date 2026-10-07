// P2.5 S2 (146): "Approve & schedule" next to Approve → sheet with one row per platform (account, suggested WIB
// slots, editable time), live not-eligible notes (dry_run), Save → POST …/schedule {posts, approve} → final render.
const { test, expect, nav } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const at = (d, hm) => new Date(`${d}T${hm}:00+07:00`).toISOString();
function plan(api, over = {}) {
  api.schedulePlan = { approved: false, status: "review", campaign_name: "IME Roleplay", blocking: [], platforms: [
    { platform: "tiktok", platform_name: "TikTok", times: ["12:00", "19:00", "21:00"], post: null, accounts: [
      { id: "acc-tt", handle: "imeclips", suggestions: [at("2026-10-08", "19:00"), at("2026-10-08", "21:00"), at("2026-10-09", "12:00")] },
      { id: "acc-tt2", handle: "imespare", suggestions: [at("2026-10-08", "12:00")] }] },
    { platform: "instagram", platform_name: "Instagram Reels", times: ["11:30", "19:30"], post: null, accounts: [] },
    { platform: "youtube", platform_name: "YouTube Shorts", times: ["17:00"], accounts: [{ id: "acc-yt", handle: "imeyt", suggestions: [at("2026-10-08", "17:00")] }],
      post: { id: "p-yt", status: "planned", account_id: "acc-yt", account_handle: "imeyt", scheduled_for: at("2026-10-09", "17:00") } },
  ], ...over };
}
async function openSheet(app) {
  await nav(app, "queue");
  await app.locator('[data-queue-open="job-done"]').click();
  const cand = app.locator("#candidate-cand-a");
  await cand.locator("[data-edit]").first().click();
  await cand.locator("[data-approve-schedule]").click();
  await expect(app.locator("#scheduleSheet")).toHaveClass(/open/);
}

test("approve & schedule: suggestions in WIB, account switch, edit time, warnings, save", async ({ app, api }) => {
  plan(api);
  api.planWarn = { tiktok: "Outside IME Roleplay week window (W1–W4: 1 Oct–28 Oct)" };
  await openSheet(app);
  const tt = app.locator('[data-plan-row="tiktok"]');
  await expect(tt.locator("[data-plan-slot]")).toHaveText(["Thu 8 Oct 19:00 WIB", "Thu 8 Oct 21:00 WIB", "Fri 9 Oct 12:00 WIB"]);
  await expect(tt.locator("[data-plan-when]")).toHaveValue("2026-10-08T19:00");
  await expect(tt.locator(".plan-note")).toHaveText(/Will be recorded as not eligible: Outside IME Roleplay/);
  await expect(app.locator('[data-plan-row="instagram"]')).toContainText("No active Instagram Reels account");
  await expect(app.locator('[data-plan-row="youtube"] .plan-state')).toHaveText("Planned Fri 9 Oct 17:00 WIB");
  await expect(app.locator('[data-plan-row="youtube"] [data-plan-when]')).toHaveValue("2026-10-09T17:00");   // keeps its plan
  await tt.locator("[data-plan-account]").selectOption("acc-tt2");
  await expect(tt.locator("[data-plan-when]")).toHaveValue("2026-10-08T12:00");   // follows the account's suggestion
  await tt.locator("[data-plan-when]").fill("2026-10-10T20:15");
  await app.click("#scheduleSave");
  await expect(app.locator("#scheduleSheet")).not.toHaveClass(/open/);
  const save = api.calls.filter((c) => c.path === "/api/jobs/job-done/candidates/cand-a/schedule" && !c.body.dry_run).at(-1);
  expect(save.body).toEqual({ approve: true, posts: [
    { platform: "tiktok", account_id: "acc-tt2", scheduled_for: "2026-10-10T13:15:00.000Z" },
    { platform: "youtube", account_id: "acc-yt", scheduled_for: "2026-10-09T10:00:00.000Z" }] });
  expect(api.calls.some((c) => c.path.endsWith("/schedule") && c.body.dry_run)).toBe(true);
});

test("schedule: platform toggle, slot pick, blocked clip can't save", async ({ app, api }) => {
  plan(api);
  await openSheet(app);
  const tt = app.locator('[data-plan-row="tiktok"]');
  await tt.locator("[data-plan-slot]").nth(2).click();
  await expect(tt.locator("[data-plan-when]")).toHaveValue("2026-10-09T12:00");
  await expect(tt.locator("[data-plan-slot]").nth(2)).toHaveAttribute("aria-pressed", "true");
  await app.locator('[data-plan-on="tiktok"]').uncheck();
  await app.locator('[data-plan-on="youtube"]').uncheck();
  await expect(app.locator("#scheduleSave")).toBeDisabled();
  await app.keyboard.press("Escape");
  plan(api, { blocking: ["Hashtags missing or out of order"] });
  await app.locator("#candidate-cand-a [data-approve-schedule]").click();
  await expect(app.locator(".plan-block")).toContainText("Hashtags missing");
  await expect(app.locator("#scheduleSave")).toBeDisabled();
});

test("schedule sheet fits a phone (no horizontal scroll)", async ({ app, api }) => {
  plan(api);
  await openSheet(app);
  await expect(app.locator('[data-plan-row="tiktok"] [data-plan-slot]').first()).toBeVisible();
  expect(await app.evaluate(() => { const b = document.querySelector("#scheduleBody"); return b.scrollWidth <= b.clientWidth; })).toBe(true);
  await app.screenshot({ path: `test-results/schedule-sheet-${test.info().project.name}.png` });
});
