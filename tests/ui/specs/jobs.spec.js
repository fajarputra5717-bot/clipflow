const { test, expect, job, nav } = require("../fixtures");

test.describe("Job list", () => {
  test("Import list shows running jobs and patches cards in place", async ({ app, api }) => {
    api.current = [job({ id: "job-run", status: "transcribing", progress: 20, source_title: "Running mock" })];
    const card = app.locator('#currentJobs [data-job-id="job-run"]');
    await expect(card).toBeVisible({ timeout: 8_000 });
    await expect(card).toContainText("Running mock");
    const before = await card.elementHandle();
    api.current = [job({ id: "job-run", status: "analyzing", progress: 60, source_title: "Running mock" })];
    await expect.poll(async () => (await card.textContent()).toLowerCase(), { timeout: 8_000 }).toContain("analy");
    // keyed + patched (074): the same DOM node, not a re-render
    expect(await before.evaluate((n) => n.isConnected)).toBe(true);
    expect(await card.evaluate((n, b) => n === b, before)).toBe(true);
  });

  test("Review list renders history and opens a job", async ({ app }) => {
    await nav(app, "queue");
    await expect(app.locator("#pageTitle")).toHaveText("Review");
    const row = app.locator('[data-queue-open="job-done"]');
    await expect(row).toBeVisible();
    await row.click();
    await expect(app.locator("#queueDetail")).toBeVisible();
    await expect(app.locator("#candidate-cand-a")).toBeVisible();
  });
});
