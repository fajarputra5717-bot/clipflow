const { test, expect } = require("../fixtures");

// 117: a campaign's default_layout pre-selects the facecam layout unless the user picked one.
test.describe("Campaign default layout", () => {
  test("IME selects No facecam; back to None resets Auto; an explicit pick wins", async ({ app }) => {
    await app.locator("#importOptions > summary").click();
    await app.locator("#jobCampaign").selectOption("ime-roleplay");
    await expect(app.locator('[data-layout="none"]')).toHaveClass(/active/);
    await app.locator("#jobCampaign").selectOption("");
    await expect(app.locator('[data-layout="auto"]')).toHaveClass(/active/);
    await app.locator('[data-layout="right"]').click();
    await app.locator("#jobCampaign").selectOption("ime-roleplay");
    await expect(app.locator('[data-layout="right"]')).toHaveClass(/active/);
  });
});
