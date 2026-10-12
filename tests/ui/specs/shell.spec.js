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
