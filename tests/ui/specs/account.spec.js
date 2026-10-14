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
  expect(bar.height).toBeLessThanOrEqual(56);   // UI task phase 1: --appbar-h 48 → 56 (×1.2)
  expect(pill.y + pill.height).toBeLessThanOrEqual(480);
  expect(pill.y).toBeGreaterThan(400);
  await expect(app.locator("#flow li.active button")).toHaveAccessibleName(/Analyze/);
  // UI phase 1 item 2: icon dock; the name is a tooltip on hover/focus (desktop), hidden at rest
  const tip = app.locator("#flow li.active .flow-label");
  expect(await tip.evaluate((e) => getComputedStyle(e).opacity)).toBe("0");
  if (app.viewportSize().width > 600) {
    await app.locator("#flow li.active button").hover();
    await expect.poll(() => tip.evaluate((e) => getComputedStyle(e).opacity)).toBe("1");
  }
});

// UI phase 1 item 5: the menu has no Watermarks / Settings (top-bar icons) in either theme, no Refresh, and the version is
// a plain label beside "What's new". Phones (no room for those icons beside the island) get the two items in the menu.
test("account menu: no duplicates of the top-bar icons, no Refresh, version as a label", async ({ app }) => {
  const phone = test.info().project.name === "mobile";
  for (const theme of ["light", "dark"]) {
    await app.evaluate((t) => window.applyTheme(t), theme);
    await app.click("#accountMenuBtn");
    await expect(app.locator("#accountMenu")).toHaveClass(/open/);
    await expect(app.locator('#accountMenu [data-nav="watermarks"]')).toHaveCount(phone ? 1 : 0);
    await expect(app.locator('#accountMenu [data-nav="settings"]')).toHaveCount(phone ? 1 : 0);
    if (!phone) await expect(app.locator('#toolbar .icon-btn[data-nav="settings"]')).toBeVisible();
    await expect(app.locator("#refreshView")).toHaveCount(0);
    await expect(app.locator("#accountMenu .acct-new summary")).toContainText("What's new");
    const ver = app.locator("#versionBadge");
    await expect(ver).toHaveClass(/acct-ver/);
    await expect(ver).toHaveText(/^v3\.\d{3,}$/);                                     // item 6: v3.<highest change number>
    await app.locator("#accountMenu .acct-new summary").click();
    await expect(app.locator("#whatsNewList li")).toHaveCount(5);
    await expect(app.locator("#whatsNewList li").first()).toContainText((await ver.textContent()).replace("v3.", ""));
    expect(await ver.evaluate((e) => getComputedStyle(e).borderTopWidth + getComputedStyle(e).backgroundColor)).toMatch(/^0px(rgba\(0, 0, 0, 0\)|transparent)/);
    await app.keyboard.press("Escape");
  }
});
