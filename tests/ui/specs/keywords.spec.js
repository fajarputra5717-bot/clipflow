const { test, expect, nav, classicQueue } = require("../fixtures");

// 111 (P1): keyword highlight — tap a caption word to toggle it, pick a colour, Apply sends edit_spec.
test.use({ reducedMotion: "reduce" });
test.describe("Keyword highlight", () => {
  test("toggle a word in the strip, choose green, Apply sends keywords + keyword_color", async ({ app, api }) => {
    await classicQueue(app);
    await app.locator('[data-queue-open="job-done"]').click();
    const cand = app.locator("#candidate-cand-a");
    await cand.locator("[data-edit]").first().click();
    const word = cand.locator('[data-kw-toggle="caption"]');
    await expect(word).toHaveAttribute("aria-pressed", "false");
    await word.click();
    await expect(word).toHaveAttribute("aria-pressed", "true");
    await expect(cand.locator("#capPreviewText-cand-a .kw")).toHaveText("CAPTION");
    await cand.locator('[data-kw-color="#30D158"]').click();
    await cand.locator("[data-apply]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "PATCH" && c.body?.edit_spec?.keywords)).toBe(true);
    const p = api.calls.find((c) => c.method === "PATCH" && c.body?.edit_spec?.keywords);
    expect(p.body.edit_spec.keywords).toEqual(["caption"]);
    expect(p.body.edit_spec.keyword_color).toBe("#30D158");
  });
});

// 112 (P1): per-clip caption position.
test.describe("Caption position", () => {
  test("custom position sends edit_spec.caption_y; back to Auto sends null", async ({ app, api }) => {
    await classicQueue(app);
    await app.locator('[data-queue-open="job-done"]').click();
    const cand = app.locator("#candidate-cand-a");
    await cand.locator("[data-edit]").first().click();
    const range = cand.locator("#capy-cand-a");
    await expect(range).toBeDisabled();
    await cand.locator("#capyon-cand-a").check();
    await expect(range).toBeEnabled();
    await range.fill("62");
    await expect(cand.locator("#capyVal-cand-a")).toHaveText("62 %");
    await cand.locator("[data-apply]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "PATCH" && c.body?.edit_spec?.caption_y === 62)).toBe(true);
  });
});
