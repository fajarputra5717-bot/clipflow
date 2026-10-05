// P1.5 login: signed out → login screen only (app, tab bar and island hidden + inert); wrong password shows the
// server's message; right password opens the app without a reload; Sign out returns to the login screen.
const base = require("@playwright/test");
const { mockApi, newState, blockingProblems } = require("../fixtures");
const { test, expect } = base;

test("login screen, wrong + right password, sign out", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => { errors.push("dialog: " + d.message()); d.dismiss(); });
  const api = newState(); api.user = null;
  await mockApi(page, api);
  await page.goto("/");
  await expect(page.locator("#loginScreen")).toBeVisible();
  await expect(page.locator("#appShell")).toBeHidden();
  expect(await page.locator("#appShell").evaluate((el) => el.inert)).toBe(true);
  expect(api.calls.some((c) => c.path === "/api/jobs")).toBe(false); // nothing loads before sign-in
  expect(await blockingProblems(page, ["#loginUser", "#loginPass", "#loginSubmit"])).toEqual([]);

  await page.fill("#loginUser", "member1");
  await page.fill("#loginPass", "wrong password");
  await page.click("#loginSubmit");
  await expect(page.locator("#loginError")).toHaveText("Wrong username or password");
  await expect(page.locator("#loginScreen")).toBeVisible();

  await page.fill("#loginPass", "correct horse");
  await page.click("#loginSubmit");
  await expect(page.locator("#loginScreen")).toBeHidden();
  await page.waitForResponse((r) => r.url().includes("/api/jobs?scope=current"));
  await expect(page.locator("#pageTitle")).toHaveText("Analyze");
  await expect(page.locator("#accountName")).toHaveText("member1");

  await page.evaluate(() => document.querySelector("[data-signout]").click());
  await expect(page.locator("#loginScreen")).toBeVisible();
  expect(api.calls.some((c) => c.path === "/api/auth/logout")).toBe(true);
  expect(errors).toEqual([]);
});
