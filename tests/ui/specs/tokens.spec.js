// P1.5 part 4: API tokens in the Account sheet: create (name required, plaintext shown once), list, two-step revoke.
const { test, expect, openAccount } = require("../fixtures");

test("create, show once, list and revoke an API token", async ({ app, api }) => {
  await openAccount(app);
  await expect(app.locator("#tokenList")).toContainText("No tokens yet.");
  await app.click("#tokenCreate");
  await expect(app.locator("#tokenMsg")).toHaveText("Give the token a name.");
  await app.fill("#tokenName", "n8n import");
  await app.click("#tokenCreate");
  await expect(app.locator("#tokenNew")).toBeVisible();
  await expect(app.locator("#tokenValue")).toHaveValue("cf_mock123-full-secret");
  await expect(app.locator("#tokenList li")).toHaveCount(1);
  await expect(app.locator("#tokenList")).toContainText("n8n import");
  await expect(app.locator("#tokenList")).not.toContainText("full-secret"); // list never shows the secret
  const revoke = app.locator("[data-token-revoke]");
  await revoke.click();
  await expect(revoke).toHaveText("Confirm revoke");
  expect(api.calls.some((c) => c.method === "DELETE")).toBe(false);
  await revoke.click();
  await expect(app.locator("#tokenMsg")).toHaveText("Token revoked.");
  await expect(app.locator("#tokenList")).toContainText("No tokens yet.");
  // Re-opening the sheet hides the old plaintext.
  await app.keyboard.press("Escape");
  await openAccount(app);
  await expect(app.locator("#tokenNew")).toBeHidden();
});
