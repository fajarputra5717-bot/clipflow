// P1.5 Account sheet: username in the sidebar opens it; change password validates inline (12+ chars, confirm
// match), shows the server's error inline, succeeds; Sign out is there too. Stepper stays fully visible when
// scrolled (sticky under the toolbar, compact once it collapses).
const { test, expect, openAccount } = require("../fixtures");

test("account sheet: inline validation, server error, success", async ({ app, api }) => {
  await app.route("**/api/auth/password", (r) => {
    const b = r.request().postDataJSON();
    api.calls.push({ method: "POST", path: "/api/auth/password", body: b });
    return b.current_password === "old password!!"
      ? r.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' })
      : r.fulfill({ status: 400, contentType: "application/json", body: '{"detail":"Current password is wrong"}' });
  });
  await openAccount(app);
  await expect(app.locator("#accountSheet")).toHaveClass(/open/);
  await expect(app.locator("#accountWho")).toContainText("admin");
  await app.fill("#pwCurrent", "old password!!");
  await app.fill("#pwNew", "short");
  await app.click("#pwSubmit");
  await expect(app.locator("#pwMsg")).toHaveText(/at least 12 characters/);
  await app.fill("#pwNew", "a much longer secret");
  await app.fill("#pwConfirm", "a different secret!");
  await app.click("#pwSubmit");
  await expect(app.locator("#pwMsg")).toHaveText(/don't match/);
  await app.fill("#pwCurrent", "wrong old one");
  await app.fill("#pwConfirm", "a much longer secret");
  await app.click("#pwSubmit");
  await expect(app.locator("#pwMsg")).toHaveText("Current password is wrong");
  await app.fill("#pwCurrent", "old password!!");
  await app.click("#pwSubmit");
  await expect(app.locator("#pwMsg")).toHaveText(/Password changed/);
  await expect(app.locator("#pwNew")).toHaveValue("");
  await expect(app.locator("#accountSheet [data-signout]")).toBeVisible();
  await app.keyboard.press("Escape");
  await expect(app.locator("#accountSheet")).not.toHaveClass(/open/);
});

test("169: top bar stays at the top and the stepper pill at the bottom when scrolled", async ({ app }) => {
  await app.setViewportSize({ width: app.viewportSize().width, height: 480 });
  await app.evaluate(() => scrollTo({ top: 200, behavior: "instant" }));
  const bar = await app.locator("#toolbar").boundingBox(), pill = await app.locator("#flowNav").boundingBox();
  expect(Math.round(bar.y)).toBe(0);
  expect(bar.height).toBeLessThanOrEqual(48);
  expect(pill.y + pill.height).toBeLessThanOrEqual(480);
  expect(pill.y).toBeGreaterThan(400);
  await expect(app.locator("#flow li.active .flow-label")).toBeVisible();
  await expect(app.locator("#flow li:not(.active) .flow-label").first()).toBeHidden();
});
