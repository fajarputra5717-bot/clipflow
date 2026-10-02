const { test, expect, nav } = require("../fixtures");

// 109 (P1): campaign rule chips + "Fix N rules to approve" gate; content check is a warning only.
test.use({ reducedMotion: "reduce" });
test.describe("Campaign rule chips", () => {
  test("failing hashtag rule disables Approve; Add hashtags posts fix-rule; content warning offers Dismiss", async ({ app, api }) => {
    const cand = api.jobs["job-done"].candidates[0];
    cand.rule_checks = [
      { id: "length", ok: true, blocking: true, label: "Length 34 s", detail: "", fix: null },
      { id: "hashtags", ok: false, blocking: true, label: "Hashtags missing or out of order", detail: "Ends with: #a #b", fix: "hashtags" },
      { id: "safety", ok: false, blocking: false, label: "Content check: 1 possible issue", detail: "[no_sara] “x”: y", fix: "dismiss" },
    ];
    await nav(app, "queue");
    await app.locator('[data-queue-open="job-done"]').click();
    const card = app.locator("#candidate-cand-a");
    await expect(card.locator(".rule-chip")).toHaveCount(3);
    await expect(card.locator(".rule-chip.bad")).toContainText("Hashtags");
    await expect(card.locator(".rule-chip.warn")).toContainText("Content check");
    const approve = card.locator("[data-approve]");
    await expect(approve).toBeDisabled();
    await expect(approve).toHaveText("Fix 1 rule to approve");
    await expect(card.locator('[data-rule-fix="dismiss"]')).toBeVisible();
    await card.locator('[data-rule-fix="hashtags"]').click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === "/api/jobs/job-done/candidates/cand-a/fix-rule" && c.body?.rule === "hashtags")).toBe(true);
  });
});

// 114: a final made before a render-affecting change is marked outdated.
test.describe("Outdated final chip", () => {
  test("render warning final_outdated shows 'Final outdated · re-render'", async ({ app, api }) => {
    api.jobs["job-done"].candidates[0].render_warnings = [{ code: "final_outdated", message: "Final outdated · re-render" }];
    await nav(app, "queue");
    await app.locator('[data-queue-open="job-done"]').click();
    await expect(app.locator("#candidate-cand-a .render-warn")).toContainText("Final outdated · re-render");
  });
});
