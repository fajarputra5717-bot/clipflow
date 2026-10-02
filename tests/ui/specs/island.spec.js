const { test, expect, job } = require("../fixtures");

test.describe("Job status island", () => {
  test("hidden when idle, appears while a job runs, celebrates when it finishes", async ({ app, api }) => {
    const island = app.locator("#island");
    await expect(island).toBeHidden();
    api.current = [job({ id: "run-1", status: "transcribing", progress: 40, source_title: "Island mock" })];
    await expect(island).toBeVisible({ timeout: 8_000 });
    await expect(app.locator("#islTitleC")).toContainText("Island mock");
    await expect(app.locator("#islandMain")).toHaveAttribute("aria-label", /40%/);
    // finished → review: the island fires the "ready" event (auto-expands), then goes away
    const done = job({ id: "run-1", status: "review", progress: 100, source_title: "Island mock" });
    api.jobs["run-1"] = done;
    api.current = [done];
    await expect(app.locator("#islandMain")).toHaveAttribute("aria-expanded", "true", { timeout: 8_000 });
    await expect(island).toBeHidden({ timeout: 10_000 });
  });
});
