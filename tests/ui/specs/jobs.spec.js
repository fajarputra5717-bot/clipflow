const { test, expect, job, nav, classicQueue } = require("../fixtures");

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
    await classicQueue(app);
    await expect(app.locator("#pageTitle")).toHaveText("Review");
    const row = app.locator('[data-queue-open="job-done"]');
    await expect(row).toBeVisible();
    await row.click();
    await expect(app.locator("#queueDetail")).toBeVisible();
    await expect(app.locator("#candidate-cand-a")).toBeVisible();
  });
});

test("Review cards show the first clip's thumbnail from thumb_candidate_id (135)", async ({ app, api }) => {
  api.queue = api.queue.map((j) => ({ ...j, thumb_candidate_id: "cand-a", candidates: undefined }));
  await app.locator('[data-nav="queue"] >> visible=true').first().click();
  await expect(app.locator('[data-queue-open="job-done"] .queue-thumb img')).toHaveAttribute("src", /\/api\/jobs\/job-done\/candidates\/cand-a\/thumbnail/);
});

test("172: Analyze cards are compact: thumbnail, title, status chip, campaign, date; the card opens #review/<job>", async ({ app, api }) => {
  api.current = [job({ id: "job-c", status: "review", source_title: "Compact mock", campaign: "ime-roleplay", thumb_candidate_id: "cand-a" })];
  const card = app.locator('#currentJobs [data-job-id="job-c"]');
  await expect(card).toBeVisible({ timeout: 8_000 });
  await expect(card.locator("h3")).toHaveText("Compact mock");
  await expect(card.locator(".jc-meta .badge")).toBeVisible();
  await expect(card.locator(".jc-thumb img")).toHaveAttribute("src", /\/api\/jobs\/job-c\/candidates\/cand-a\/thumbnail/);
  await expect(app.locator(":text('Tap a job to review'), :text('Click anywhere to review')")).toHaveCount(0);
  await expect(card.locator(".jc-link")).toHaveAttribute("href", "#review/job-c");
});
