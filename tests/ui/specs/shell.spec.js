const { test, expect, classicQueue } = require("../fixtures");

// UI shell (P1 task 0): the flow-preview stepper is the top-level navigation.
test.describe("UI shell stepper", () => {
  test.use({ reducedMotion: "reduce" });
  test("8 steps; unbuilt ones disabled with their phase; Analyze → Review → Editor; gear opens Settings", async ({ app }) => {
    const steps = app.locator("#flow li");
    await expect(steps).toHaveCount(8);
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Analyze");
    await expect(app.locator("#pageTitle")).toHaveText("Analyze");
    for (const [label, phase] of [["Auto-import", "P3"], ["Track", "P3"]]) {
      const li = app.locator("#flow li", { has: app.locator(".flow-label", { hasText: new RegExp(`^${label}$`) }) });
      await expect(li.locator("button")).toBeDisabled();
      await expect(li.locator(".flow-sub")).toHaveText(`Coming in ${phase}`);
    }
    const editor = app.locator("#flow [data-flow-editor]");
    await expect(editor).toBeDisabled();
    await app.locator('#flow [data-nav="queue"]').click();               // 149: Review = the Review page
    await expect(app.locator("#reviewSection")).toBeVisible();
    await expect(app.locator("#pageTitle")).toHaveText("Review");
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Review");
    await classicQueue(app);                                           // the old panel ("All edits" path)
    await app.locator('[data-queue-open="job-done"]').click();
    await expect(app.locator("#candidate-cand-a")).toBeVisible();
    await expect(editor).toBeEnabled();
    await editor.click();
    await expect(app.locator("#candidate-cand-a")).toHaveClass(/editing/);
    await expect(app.locator("#flow li.active .flow-label")).toHaveText("Editor");
    await expect(app.locator("#pageTitle")).toHaveText("Editor");
    await app.locator('#flow [data-nav="current"]').click();
    await expect(app.locator("#pageTitle")).toHaveText("Analyze");
    await app.locator('.toolbar [data-nav="settings"]').click();
    await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
  });
});
