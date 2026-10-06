const { test, expect } = require("../fixtures");

test.describe("Import form", () => {
  test("validates the URL and enables Start analysis only for a YouTube link", async ({ app }) => {
    const url = app.locator("#youtubeUrl"), go = app.locator("#analyzeButton");
    await expect(go).toBeDisabled();
    await expect(go).toHaveText("Start analysis");
    await url.fill("https://example.com/video");
    await expect(url).toHaveAttribute("aria-invalid", "true");
    await expect(app.locator("#youtubeUrlHint")).toHaveClass(/is-error/);
    await expect(go).toBeDisabled();
    await url.fill("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    await expect(url).toHaveAttribute("aria-invalid", "false");
    await expect(go).toBeEnabled();
    await expect(app.locator("#urlPreviewId")).toHaveText("dQw4w9WgXcQ");
  });

  test("the language choice is sent with the job", async ({ app, api }) => {
    await app.locator('[data-language="en"]').click();
    await expect(app.locator('[data-language="en"]')).toHaveAttribute("aria-pressed", "true");
    await app.locator("#youtubeUrl").fill("https://youtu.be/dQw4w9WgXcQ");
    await app.locator("#analyzeButton").click();
    await expect.poll(() => api.calls.find((c) => c.method === "POST" && c.path === "/api/jobs")?.body)
      .toMatchObject({ youtube_url: "https://youtu.be/dQw4w9WgXcQ", language: "en" });
    await expect(app.locator('#currentJobs [data-job-id="job-new"]')).toBeVisible();
  });
});
