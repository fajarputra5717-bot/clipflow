const { test, expect, nav } = require("../fixtures");

// UI shell (P1 task 0): the flow-preview stepper is the top-level navigation.
test.describe("UI shell stepper", () => {
  test.use({ reducedMotion: "reduce" });
  test("8 steps, all live (183); Analyze → Review → Editor; gear opens Settings", async ({ app }) => {
    const steps = app.locator("#flow li");
    await expect(steps).toHaveCount(8);
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Analyze");
    await expect(app.locator("#pageTitle")).toHaveText("Analyze");
    await expect(app.locator("#flow li button:disabled")).toHaveCount(0);   // 181 Track, 183 Auto-import: every step is live
    const editor = app.locator("#flow [data-flow-editor]");
    await expect(editor).toBeEnabled();                                  // 171: no clip yet → Pick a clip
    await app.locator('#flow [data-nav="queue"]').click();               // 149: Review = the Review page
    await expect(app.locator("#reviewSection")).toBeVisible();
    await expect(app.locator("#pageTitle")).toHaveText("Review");
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Review");
    await editor.click();                                              // 171: no clip yet → Pick a clip
    await expect(app.locator("#pickSection")).toBeVisible();
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Editor");
    await expect(app.locator("#pageTitle")).toHaveText("Editor");
    await app.locator('#flow [data-nav="current"]').click();
    await expect(app.locator("#pageTitle")).toHaveText("Analyze");
    await nav(app, "settings");
    await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
  });
});

// UI phase 1 item 4: one title per page. The top bar shows no page name; each page's own heading is the title.
test("top bar repeats no page title; every page shows its own heading", async ({ app }) => {
  for (const [go, heading] of [[() => window.showTab("schedule"), "#scheduleSection"], [() => window.showTab("campaign"), "#campaignSection"],
                                 [() => { location.hash = "#track"; }, "#trackSection"], [() => window.showTab("current"), "#currentSection"]]) {
    await app.evaluate(go);
    await app.waitForTimeout(400);
    await expect(app.locator("#pageContext")).toBeHidden();
    expect(await app.evaluate(() => [...document.querySelectorAll("#toolbar *")].filter((e) => !e.closest(".sr-only") && e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && !e.children.length).map((e) => e.textContent.trim()).join(" "))).not.toMatch(/Schedule|Campaign|Track|Analyze/);   // sr-only #pageTitle stays
    await expect(app.locator(`${heading} :is(h1,h2,h3)`).first()).toBeVisible();
  }
});

// UI phase 1 item 8: every page intro is one line (desktop and 390 phones); the longer explanation opens from an info button.
test("page intros are one line; the info button shows the rest", async ({ app }) => {
  for (const go of [() => window.showTab("campaign"), () => window.showTab("current"), () => window.showTab("schedule"), () => { location.hash = "#import"; },
                    () => { location.hash = "#track"; }, () => window.showTab("publish"), () => { location.hash = "#editor"; }]) {
    await app.evaluate(go); await app.waitForTimeout(500);
    const intro = app.locator(".view-section:not(.hidden) .section-head .page-intro, #pickSection:not(.hidden) .page-intro").first();
    await expect(intro).toBeVisible();
    const [h, lh] = await intro.evaluate((e) => [e.getBoundingClientRect().height, parseFloat(getComputedStyle(e).lineHeight) || 20]);
    expect(h, await intro.textContent()).toBeLessThanOrEqual(Math.max(lh * 1.5, 30));
    const btn = intro.locator("[data-info]");
    if (await btn.count()) {
      const panel = app.locator(`#${await btn.getAttribute("aria-controls")}`);
      await expect(panel).toBeHidden();
      await btn.click();
      await expect(panel).toBeVisible(); await expect(btn).toHaveAttribute("aria-expanded", "true");
      await btn.click();
      await expect(panel).toBeHidden(); await expect(btn).toHaveAttribute("aria-expanded", "false");
      await btn.click(); await expect(panel).toBeVisible();
      await app.keyboard.press("Escape");                                       // QA Low: Esc closes it
      await expect(panel).toBeHidden(); await expect(btn).toBeFocused();
    }
  }
});
