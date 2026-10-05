// P1.5 part 3: the Settings sheet renders only the keys the API returns (members: user-level keys only) and
// labels where each value comes from; a member's save sends only the changed user key.
const { test, expect } = require("../fixtures");

test.use({});
test("member sees only user-level settings, labelled Yours / House default", async ({ app, api }) => {
  api.user = { id: "u-m", username: "member1", role: "member" };
  api.settings = {
    WATERMARK_WIDTH: { value: "300", configured: true, source: "user", scope: "user" },
    FULLFRAME_CAPTION_Y: { value: "78", configured: true, source: "db", scope: "user" },
    HASHTAGS: { value: "", configured: false, source: "default", scope: "user" },
  };
  await app.reload();
  await app.waitForResponse((r) => r.url().includes("/api/settings"));
  await app.locator('[data-nav="settings"] >> visible=true').first().click();
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
  await expect(app.locator("[data-setting]")).toHaveCount(3);
  await expect(app.locator("#set-WHISPER_MODEL")).toHaveCount(0);
  await expect(app.locator('label[for="set-WATERMARK_WIDTH"] small')).toContainText("Yours");
  await expect(app.locator('label[for="set-FULLFRAME_CAPTION_Y"] small')).toContainText("House default");
  await app.fill("#set-WATERMARK_WIDTH", "320");
  await app.click("#saveSettings");
  await expect.poll(() => api.calls.find((c) => c.method === "PUT" && c.path === "/api/settings")?.body).toEqual({ values: { WATERMARK_WIDTH: "320" } });
});
