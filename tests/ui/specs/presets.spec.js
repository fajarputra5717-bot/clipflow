const { test, expect, nav } = require("../fixtures");

// The edit drawer is tall (P1 presets): clicking its tabs makes Playwright scroll, and the app's
// html{scroll-behavior:smooth} turns that into an animated scroll that never settles under suite load.
// Reduced motion switches smooth scrolling off (app CSS) — the drawer itself is what's under test.
test.use({ reducedMotion: "reduce" });

// 108 (P1): caption preset cards set THIS clip's style + animation; Apply stores them as the clip's own
// preset (edit_spec.caption) and leaves the job-level style alone.
test.describe("Caption presets", () => {
  test("picking a card sets the selects and Apply sends edit_spec.caption, job style unchanged", async ({ app, api }) => {
    await nav(app, "queue");
    await app.locator('[data-queue-open="job-done"]').click();
    const cand = app.locator("#candidate-cand-a");
    await cand.locator("[data-edit]").first().click();
    const neon = cand.locator('[data-preset="neon"]');
    await expect(cand.locator("[data-preset]")).toHaveCount(6);
    await neon.click();
    await expect(neon).toHaveAttribute("aria-pressed", "true");
    await expect(cand.locator("#style-cand-a")).toHaveValue("neon");
    await expect(cand.locator("#anim-cand-a")).toHaveValue("typewriter");
    await cand.locator("[data-apply]").click();
    await expect.poll(() => api.calls.filter((c) => c.method === "PATCH").length).toBeGreaterThanOrEqual(3);
    const cpatch = api.calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/job-done/candidates/cand-a" && c.body?.edit_spec);
    expect(cpatch.body.edit_spec).toEqual({ caption: { style: "neon", animation: "typewriter" } });
    const jpatch = api.calls.find((c) => c.method === "PATCH" && c.path === "/api/jobs/job-done/subtitle-style");
    expect(jpatch.body.subtitle_style).toBe("bold");
    expect(jpatch.body.subtitle_animation).toBe("karaoke");
  });
});
