const { test, expect, nav, blockingProblems, classicQueue } = require("../fixtures");

// The edit drawer is tall (P1 presets): clicking its tabs makes Playwright scroll, and the app's
// html{scroll-behavior:smooth} turns that into an animated scroll that never settles under suite load.
// Reduced motion switches smooth scrolling off (app CSS) — the drawer itself is what's under test.
test.use({ reducedMotion: "reduce" });

test.describe("Edit panel", () => {
  test("opens, switches tab, closes, and leaves the page clickable", async ({ app }) => {
    await classicQueue(app);
    await app.locator('[data-queue-open="job-done"]').click();
    const cand = app.locator("#candidate-cand-a"), toggle = cand.locator("[data-edit]").first();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await toggle.click();
    await expect(cand).toHaveClass(/editing/);
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(cand.locator(".edit-drawer")).toBeVisible();
    const tabs = cand.locator("[data-edit-tab]");
    if (await tabs.count() > 1) {
      await tabs.nth(1).click();
      await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
    }
    await toggle.click();
    await expect(cand).not.toHaveClass(/editing/);
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(cand.locator(".edit-drawer")).toBeHidden();
    expect(await blockingProblems(app, ['[data-nav="current"]', "#candidate-cand-b [data-edit]"])).toEqual([]);
  });
});
