const { test, expect, mockReviewClips } = require("../fixtures");

// 109 (P1): campaign rule chips gate Approve; the content check is a warning only. 179: on the Review page (the old
// drawer is gone), plus the non-fatal render warnings (114: "Final outdated · re-render") ported from the drawer.
test.use({ reducedMotion: "reduce" });
test.describe("Campaign rule chips on Review", () => {
  test("failing hashtag rule disables Approve; Add tags posts fix-rule; content warning offers Dismiss", async ({ app, api }) => {
    await mockReviewClips(app, api, [{ id: "cand-a", rule_checks: [
      { id: "length", ok: true, blocking: true, label: "Length 34 s", detail: "", fix: null },
      { id: "hashtags", ok: false, blocking: true, label: "Hashtags missing or out of order", detail: "Ends with: #a #b", fix: "hashtags" },
      { id: "safety", ok: false, blocking: false, label: "Content check: 1 possible issue", detail: "[no_sara] “x”: y", fix: "dismiss" },
    ] }]);
    const card = app.locator("#rv-cand-a");
    await expect(card.locator(".rv-checks .badge")).toHaveCount(2);                 // owner 2026-10-14: failing checks only
    await expect(card.locator(".rv-checks")).not.toContainText("Length");
    await expect(card.locator(".badge.failed")).toContainText("Hashtags");
    await expect(card.locator(".badge.attention")).toContainText("Content check");
    await expect(card.locator("[data-rv-approve]")).toBeDisabled();
    await expect(card.locator('[data-rv-fix="dismiss"]')).toBeVisible();
    await card.locator('[data-rv-fix="hashtags"]').click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === "/api/jobs/job-done/candidates/cand-a/fix-rule" && c.body?.rule === "hashtags")).toBe(true);
  });

  test("every check passes: one 'All rules pass' chip (its title lists the rules), no hint line", async ({ app, api }) => {
    await mockReviewClips(app, api, [{ id: "cand-a", rule_checks: [
      { id: "length", ok: true, blocking: true, label: "Length 34 s", detail: "", fix: null },
      { id: "hashtags", ok: true, blocking: true, label: "Hashtags", detail: "", fix: null },
    ] }]);
    const chips = app.locator("#rv-cand-a .rv-checks .badge");
    await expect(chips).toHaveCount(1);
    await expect(chips).toHaveText("✓ All rules pass");
    await expect(chips).toHaveAttribute("title", "✓ Length 34 s\n✓ Hashtags");
    await expect(app.locator("#rv-cand-a .rv-hint")).toHaveCount(0);
    await expect(app.locator("#rv-cand-a [data-rv-approve]")).toBeEnabled();
  });

  test("render warning final_outdated shows 'Final outdated · re-render' on the card", async ({ app, api }) => {
    await mockReviewClips(app, api, [{ id: "cand-a", render_warnings: [{ code: "final_outdated", message: "Final outdated · re-render" }] }]);
    await expect(app.locator("#rv-cand-a .render-warn")).toContainText("Final outdated · re-render");
  });
});
