const { test, expect } = require("../fixtures");

// 117/126: a campaign's default_layout (and default_language) pre-select the form, tagged "from campaign",
// unless the user picked one.
test.describe("Campaign defaults", () => {
  test("IME selects Full frame; back to None resets facecam Auto; an explicit pick wins", async ({ app }) => {
    const full = app.locator('[data-layout-card="full"]'), cam = app.locator('[data-layout-card="facecam"]');
    await app.locator("#jobCampaign").selectOption("ime-roleplay");
    await expect(full).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#layoutFromCampaign")).toBeVisible();
    await expect(app.locator("#facecamOpts")).toBeHidden();
    await app.locator("#jobCampaign").selectOption("");
    await expect(cam).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator('[data-layout="auto"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#layoutFromCampaign")).toBeHidden();
    await app.locator('[data-layout="right"]').click();
    await app.locator("#jobCampaign").selectOption("ime-roleplay");
    await expect(app.locator('[data-layout="right"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#layoutFromCampaign")).toBeHidden();
  });

  test("a campaign language pre-fills Indonesian (from campaign) without becoming the remembered fallback", async ({ app }) => {
    await app.locator("#jobCampaign").selectOption("windah");
    await expect(app.locator('[data-language="id"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#langFromCampaign")).toBeVisible();
    expect(await app.evaluate(() => localStorage.getItem("clipflow_last_language"))).toBeNull();
    await app.locator("#jobCampaign").selectOption("");
    await expect(app.locator('[data-language="auto"]')).toHaveAttribute("aria-pressed", "true");
    await app.locator('[data-language="en"]').click();
    await app.locator("#jobCampaign").selectOption("windah");
    await expect(app.locator('[data-language="en"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#langFromCampaign")).toBeHidden();
  });
});
