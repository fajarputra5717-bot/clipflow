// P2 part 1: posting accounts in Settings (any user): add (handle required, @ stripped, duplicate → server message),
// pause/resume, two-step remove.
const { test, expect } = require("../fixtures");

test("add, duplicate, pause/resume and remove a posting account", async ({ app, api }) => {
  await app.locator('[data-nav="settings"] >> visible=true').first().click();
  await expect(app.locator("#accountsAdmin")).toBeVisible();
  await expect(app.locator("#accountsList")).toContainText("No posting accounts yet.");
  await app.click("#accountCreateBtn");
  await expect(app.locator("#accountsMsg")).toHaveText("Enter the account handle.");
  await app.locator("#newAccountPlatform").selectOption("tiktok");
  await app.fill("#newAccountHandle", "@imeclips");
  await app.fill("#newAccountNote", "IME");
  await app.click("#accountCreateBtn");
  await expect(app.locator("#accountsMsg")).toHaveText("Added @imeclips.");
  expect(api.calls.find((c) => c.method === "POST" && c.path === "/api/accounts").body).toEqual({ platform: "tiktok", handle: "imeclips", note: "IME" });
  await app.fill("#newAccountHandle", "IMECLIPS");
  await app.click("#accountCreateBtn");
  await expect(app.locator("#accountsMsg")).toContainText("already have");
  const row = app.locator('[data-account-row="acc-imeclips"]');
  await row.locator("[data-account-active]").click();
  await expect(row).toContainText("Paused");
  await row.locator("[data-account-active]").click();
  await expect(row).not.toContainText("Paused");
  const rm = row.locator("[data-account-remove]");
  await rm.click(); await expect(rm).toHaveText("Confirm remove");
  await rm.click();
  await expect(app.locator("#accountsList")).toContainText("No posting accounts yet.");
});
