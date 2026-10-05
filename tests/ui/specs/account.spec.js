// P1.5 Account sheet: username in the sidebar opens it; change password validates inline (12+ chars, confirm
// match), shows the server's error inline, succeeds; Sign out is there too. Stepper stays fully visible when
// scrolled (sticky under the toolbar, compact once it collapses).
const { test, expect } = require("../fixtures");

test("account sheet: inline validation, server error, success", async ({ app, api }) => {
  await app.route("**/api/auth/password", (r) => {
    const b = r.request().postDataJSON();
    api.calls.push({ method: "POST", path: "/api/auth/password", body: b });
    return b.current_password === "old password!!"
      ? r.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' })
      : r.fulfill({ status: 400, contentType: "application/json", body: '{"detail":"Current password is wrong"}' });
  });
  if (test.info().project.name === "mobile") await app.click("#tabbar [data-sidebar-toggle], [data-sidebar-toggle] >> visible=true");
  await app.click("[data-account]");
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

test("stepper titles stay visible under the toolbar when scrolled", async ({ app }) => {
  await app.setViewportSize({ width: app.viewportSize().width, height: 480 });
  await app.evaluate(() => scrollTo({ top: 200, behavior: "instant" }));
  await expect(app.locator("#toolbar")).toHaveClass(/is-collapsed/);
  const bar = await app.locator("#toolbar").boundingBox();
  const label = await app.locator("#flow li.active .flow-label").boundingBox();
  expect(label.y).toBeGreaterThanOrEqual(bar.y + bar.height);
});
