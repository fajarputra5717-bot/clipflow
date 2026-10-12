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

// 184: one progress mark per task. Indeterminate = the lead spinner only (no ring, no %); a percent = the ring only
// (the lead is a thumbnail or a static dot). The compact line names the action + subject.
test.describe("Island progress mark", () => {
  test.use({ reducedMotion: "reduce" });
  const ringShown = (app) => app.locator("#islCompact .isl-ring").isVisible();

  test("indeterminate task: one spinner on the left, no ring; 'Checking @channel'", async ({ app, api }) => {
    api.activity = [{ kind: "source_check", id: "https://www.youtube.com/@windahbasudara", job_id: null, candidate_id: null, stage: "checking",
      percent: null, label: "Checking for new videos", title: "@windahbasudara" }];
    await expect(app.locator("#island")).toBeVisible({ timeout: 8_000 });
    await expect(app.locator("#islTitleC")).toHaveText("Checking @windahbasudara");
    await expect(app.locator("#islLead .isl-spinner")).toHaveCount(1);
    expect(await ringShown(app)).toBe(false);
    await expect(app.locator("#islCompact .isl-spinner")).toHaveCount(1);
    await expect(app.locator("#islandMain")).not.toHaveAttribute("aria-label", /%/);
  });

  test("task with a percent: the ring on the right, no spinner; 'Rendering <clip>'", async ({ app, api }) => {
    api.activity = [{ kind: "candidate", id: "cand-x", job_id: "job-done", candidate_id: "cand-x", stage: "rendering", percent: 40,
      label: "Final render", title: "Lompatan GILA" }];
    await expect(app.locator("#island")).toBeVisible({ timeout: 8_000 });
    await expect(app.locator("#islTitleC")).toHaveText("Rendering Lompatan GILA");
    expect(await ringShown(app)).toBe(true);
    await expect(app.locator("#island .isl-spinner")).toHaveCount(0);
    await expect(app.locator("#islandMain")).toHaveAttribute("aria-label", /40%/);
  });

  test("Telegram send reads 'Sending to phone …'", async ({ app, api }) => {
    api.activity = [{ kind: "telegram", id: "t1", job_id: "job-done", candidate_id: "cand-x", stage: "sending", percent: 30, label: "Uploading", title: "Lompatan GILA" }];
    await expect(app.locator("#islTitleC")).toHaveText("Sending to phone · Lompatan GILA", { timeout: 8_000 });
  });
});
