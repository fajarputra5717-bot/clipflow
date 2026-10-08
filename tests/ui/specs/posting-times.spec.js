// P2.5 S1: Settings → Posting times (POSTING_TIMES user setting, WIB): chips per platform, add/remove, Save sends
// the whole map, Reset sends "" (back to the defaults); the server validates (shared/schedule.py).
const { test, expect, nav } = require("../fixtures");

const DEFAULTS = '{"tiktok": ["12:00", "19:00", "21:00"], "instagram": ["11:30", "19:30"], "youtube": ["17:00", "20:00"], "facebook": ["12:00", "19:00"]}';

async function openSettings(app) {
  await nav(app, "settings");
  await expect(app.locator("#postingTimes")).toBeVisible();
}

test("posting times: defaults shown, edit, save, reset", async ({ app, api }) => {
  api.defaultPostingTimes = DEFAULTS;
  api.settings = { ...(api.settings || {}), POSTING_TIMES: { value: DEFAULTS, source: "default", scope: "user" } };
  await app.reload();
  await openSettings(app);
  const tt = app.locator('[data-ptime-row="tiktok"]');
  await expect(tt.locator(".ptime-chip")).toHaveText(["12:00✕", "19:00✕", "21:00✕"]);
  await expect(app.locator("[data-ptime-row]")).toHaveCount(4);                 // the account platforms (/api/accounts)
  await expect(app.locator("#postingTimesSave")).toBeDisabled();
  await app.locator('[data-ptime-row="facebook"] [data-ptime="12:00"]').click();
  await app.locator('[data-ptime-row="facebook"] [data-ptime="19:00"]').click();
  await expect(app.locator('[data-ptime-row="facebook"] .ptime-none')).toHaveText("No suggested times");
  await expect(app.locator("#postingTimesSave")).toBeEnabled();
  await tt.locator('[data-ptime="21:00"]').click();
  await tt.locator("[data-ptime-input]").fill("22:15");
  await tt.locator("[data-ptime-add]").click();
  await expect(tt.locator(".ptime-chip")).toHaveText(["12:00✕", "19:00✕", "22:15✕"]);
  await app.click("#postingTimesSave");
  await expect(app.locator("#postingTimesMsg")).toHaveText("Saved.");
  const put = api.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").at(-1);
  expect(JSON.parse(put.body.values.POSTING_TIMES).tiktok).toEqual(["12:00", "19:00", "22:15"]);
  expect(JSON.parse(put.body.values.POSTING_TIMES).instagram).toEqual(["11:30", "19:30"]);
  expect(JSON.parse(put.body.values.POSTING_TIMES).facebook).toEqual([]);
  await expect(app.locator("#postingTimesSave")).toBeDisabled();
  await app.click("#postingTimesReset");
  await expect(app.locator("#postingTimesMsg")).toHaveText("Back to the default times.");
  expect(api.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").at(-1).body).toEqual({ values: { POSTING_TIMES: "" } });
  await expect(tt.locator(".ptime-chip")).toHaveText(["12:00✕", "19:00✕", "21:00✕"]);
});

test("posting times: add needs a time; server errors are shown", async ({ app, api }) => {
  api.settings = { ...(api.settings || {}), POSTING_TIMES: { value: '{"tiktok": ["99:00"]}', source: "user", scope: "user" } };
  await app.reload();
  await openSettings(app);
  await app.locator('[data-ptime-row="youtube"] [data-ptime-add]').click();
  await expect(app.locator("#postingTimesMsg")).toHaveText("Pick a time first (HH:MM, WIB).");
  await app.locator('[data-ptime-row="youtube"] [data-ptime-input]').fill("08:00");
  await app.locator('[data-ptime-row="youtube"] [data-ptime-add]').click();
  await app.click("#postingTimesSave");
  await expect(app.locator("#postingTimesMsg")).toContainText("is not a time");
});

test("reminder lead (148): saved on its own as REMINDER_LEAD_MIN", async ({ app, api }) => {
  api.settings = { ...(api.settings || {}), POSTING_TIMES: { value: DEFAULTS, source: "default", scope: "user" },
    REMINDER_LEAD_MIN: { value: "15", source: "default", scope: "user" } };
  await app.reload();
  await openSettings(app);
  await expect(app.locator("#reminderLead")).toHaveValue("15");
  await app.fill("#reminderLead", "30");
  await expect(app.locator("#postingTimesSave")).toBeEnabled();
  await app.click("#postingTimesSave");
  await expect(app.locator("#postingTimesMsg")).toHaveText("Saved.");
  expect(api.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").at(-1).body).toEqual({ values: { REMINDER_LEAD_MIN: "30" } });
  await expect(app.locator("#postingTimesSave")).toBeDisabled();
});
