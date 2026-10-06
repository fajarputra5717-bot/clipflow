// P1.5 part 5: admin Users section in Settings (create with a temporary password, two-step disable, role,
// reset password, last-admin refusal shown inline) + forced password change after an admin-set password.
const base = require("@playwright/test");
const { test, expect, mockApi, newState } = require("../fixtures");

const openSettings = async (app) => {
  await app.locator('[data-nav="settings"] >> visible=true').first().click();
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
};

test("admin manages users", async ({ app, api }) => {
  api.users = [{ id: "u-admin", username: "admin", role: "admin", active: true, must_change_password: false, created_at: new Date().toISOString(), last_seen_at: null, jobs: 21, tokens: 0 }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/admin/users"));
  await openSettings(app);
  await expect(app.locator("#usersAdmin")).toBeVisible();
  await expect(app.locator("#usersList")).toContainText("admin (you)");
  // Create: validation, Generate, success
  await app.fill("#newUserName", "rina");
  await app.click("#userCreateBtn");
  await expect(app.locator("#usersMsg")).toContainText("at least 12 characters");
  await app.click('[data-gen-pass="newUserPass"]');
  expect((await app.inputValue("#newUserPass")).length).toBe(16);
  await app.click("#userCreateBtn");
  await expect(app.locator("#usersMsg")).toContainText("Created rina");
  await expect(app.locator('[data-user-row="u-rina"]')).toContainText("Temporary password");
  // Last admin can't demote themselves (409 message inline)
  await app.click('[data-user-row="u-admin"] [data-user-role]');
  await expect(app.locator("#usersMsg")).toContainText("last active admin");
  // Two-step disable
  const dis = app.locator('[data-user-row="u-rina"] [data-user-active]');
  await dis.click(); await expect(dis).toHaveText("Confirm disable");
  await dis.click();
  await expect(app.locator('[data-user-row="u-rina"]')).toContainText("Disabled");
  // Reset password
  await app.click('[data-user-row="u-rina"] [data-user-reset]');
  await app.locator('[data-user-reset-form="u-rina"] input').fill("another temp pass");
  await app.locator('[data-user-reset-form="u-rina"] button[type=submit]').click();
  await expect(app.locator("#usersMsg")).toContainText("Password reset");
  expect(api.calls.some((c) => c.path === "/api/admin/users/u-rina/reset-password" && c.body.password === "another temp pass")).toBe(true);
});

test("member never sees the Users section", async ({ app, api }) => {
  api.user = { id: "u-m", username: "member1", role: "member" };
  api.calls.length = 0; // the fixture's first load was as admin
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/jobs?scope=current"));
  await openSettings(app);
  await expect(app.locator("#usersAdmin")).toBeHidden();
  expect(api.calls.some((c) => c.path === "/api/admin/users")).toBe(false);
});

base.test("temporary password must be replaced before the app opens", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const api = newState(); api.user = null;
  await mockApi(page, api);
  await page.goto("/");
  await page.fill("#loginUser", "rina");
  await page.fill("#loginPass", "temporary pass1");
  await page.click("#loginSubmit");
  await expect(page.locator("#forceForm")).toBeVisible();
  await expect(page.locator("#forceCurrentField")).toBeHidden(); // just typed: not asked again
  await expect(page.locator("#appShell")).toBeHidden();
  expect(api.calls.some((c) => c.path === "/api/jobs")).toBe(false);
  await page.fill("#forceNew", "temporary pass1"); await page.fill("#forceConfirm", "temporary pass1");
  await page.click("#forceSubmit");
  await expect(page.locator("#forceError")).toContainText("different");
  await page.fill("#forceNew", "my own secret pw"); await page.fill("#forceConfirm", "my own secret pw");
  await page.click("#forceSubmit");
  await expect(page.locator("#loginScreen")).toBeHidden();
  await page.waitForResponse((r) => r.url().includes("/api/jobs?scope=current"));
  // After a reload with the flag still set, the temporary password is asked for.
  api.mustChange = true; await page.reload();
  await expect(page.locator("#forceForm")).toBeVisible();
  await expect(page.locator("#forceCurrentField")).toBeVisible();
  expect(errors).toEqual([]);
});
