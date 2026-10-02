// Regression: a closed overlay layer once made the whole app unclickable (CLAUDE.md, Frontend shell).
const { test, expect, job, nav, blockingProblems } = require("../fixtures");

const PROBES = ["#youtubeUrl", '[data-nav="queue"]', '[data-nav="settings"]'];

test.describe("Nothing-clickable overlay regression", () => {
  test("no layer blocks the app at rest", async ({ app }) => {
    expect(await blockingProblems(app, PROBES)).toEqual([]);
  });

  for (const sheet of ["settings", "watermarks"]) {
    test(`${sheet} sheet: close button, Escape and backdrop all release the page`, async ({ app }) => {
      const id = sheet === "settings" ? "#settingsSheet" : "#watermarkSheet";
      for (const how of ["button", "escape", "backdrop"]) {
        await nav(app, sheet);
        await expect(app.locator(id)).toHaveClass(/open/);
        if (how === "button") await app.locator(`${id} button.sheet-close`).click();
        if (how === "escape") await app.keyboard.press("Escape");
        if (how === "backdrop") await app.locator(`${id} .sheet-backdrop`).click({ position: { x: 5, y: 5 }, force: true });
        await expect(app.locator(id)).not.toHaveClass(/open/);
        await expect.poll(() => blockingProblems(app, PROBES), { message: `after closing via ${how}` }).toEqual([]);
        await expect(app.locator("#appShell")).not.toHaveAttribute("inert", "");
      }
    });
  }

  test("running-jobs overlay closes cleanly", async ({ app, api }) => {
    api.current = [job({ id: "r1", status: "transcribing", progress: 30 }),
                   job({ id: "r2", status: "analyzing", progress: 50 })];
    await expect(app.locator("#islandMore")).toBeVisible({ timeout: 8_000 });
    await app.locator("#islandMore").click();
    await expect(app.locator("#jobOverlay")).toHaveClass(/open/);
    // a hovering pointer keeps the island expanded over the overlay; a real pointer moves on
    await app.mouse.move(5, 600);
    await app.locator("#jobOverlayClose").click();
    await expect(app.locator("#jobOverlay")).not.toHaveClass(/open/);
    await expect.poll(() => blockingProblems(app, ["#youtubeUrl"])).toEqual([]);
  });

  test("version popover closes on outside click", async ({ app }, info) => {
    test.skip(info.project.name === "mobile", "badge sits in the off-canvas sidebar at 390 px");
    await app.locator("#versionBadge").click();
    await expect(app.locator("#versionPopover")).toHaveClass(/open/);
    await app.locator("#youtubeUrl").click();
    await expect(app.locator("#versionPopover")).not.toHaveClass(/open/);
    // visibility flips to hidden after the fade-out transition: poll, don't sample once
    await expect.poll(() => blockingProblems(app, PROBES)).toEqual([]);
  });

  test("mobile sidebar drawer: scrim closes it and releases the page", async ({ app }, info) => {
    test.skip(info.project.name !== "mobile", "drawer only exists at narrow widths");
    await app.locator("[data-sidebar-toggle]:visible").first().click();
    await expect(app.locator("body")).toHaveClass(/sidebar-open/);
    await app.locator("#sidebarScrim").click({ position: { x: 370, y: 400 } });
    await expect(app.locator("body")).not.toHaveClass(/sidebar-open/);
    await expect.poll(() => blockingProblems(app, ["#youtubeUrl", '#tabbar [data-nav="queue"]'])).toEqual([]);
  });
});
