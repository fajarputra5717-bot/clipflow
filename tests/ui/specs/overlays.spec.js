// Regression: a closed overlay layer once made the whole app unclickable (CLAUDE.md, Frontend shell).
const { test, expect, job, nav, blockingProblems } = require("../fixtures");

const PROBES = ["#youtubeUrl", '[data-nav="queue"]', "#accountMenuBtn"];

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

  test("169: account menu closes on outside click and on Escape, and releases the page", async ({ app }) => {
    await app.locator("#accountMenuBtn").click();
    await expect(app.locator("#accountMenu")).toHaveClass(/open/);
    await expect(app.locator("#accountMenuBtn")).toHaveAttribute("aria-expanded", "true");
    await app.mouse.click(5, 300);                                          // outside the menu (it covers the URL field on phones)
    await expect(app.locator("#accountMenu")).not.toHaveClass(/open/);
    await expect.poll(() => blockingProblems(app, PROBES)).toEqual([]);
    await app.locator("#accountMenuBtn").click();
    await app.keyboard.press("Escape");
    await expect(app.locator("#accountMenu")).not.toHaveClass(/open/);
    await expect(app.locator("#accountMenuBtn")).toBeFocused();
    await app.locator("#accountMenuBtn").click();
    await app.locator("#accountMenu .acct-new summary").click();            // What's new (version) lives in the menu
    await expect(app.locator("#accountMenu .acct-new ul")).toBeVisible();
  });
  test("182: Settings and Watermarks sheets fit a phone (no horizontal scroll), opened from the account menu", async ({ app }, info) => {
    test.skip(info.project.name !== "mobile", "phone check");
    for (const [sheet, id] of [["settings", "#settingsSheet"], ["watermarks", "#watermarkSheet"]]) {
      await nav(app, sheet);
      await expect(app.locator(id)).toHaveClass(/open/);
      const over = await app.locator(id).evaluate((el) => [...el.querySelectorAll("*")].filter((e) => e.offsetParent && e.getBoundingClientRect().right > innerWidth + 1)
        .map((e) => e.tagName.toLowerCase() + "." + [...e.classList].join(".")).slice(0, 5));
      expect(over).toEqual([]);
      expect(await app.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await app.keyboard.press("Escape");
      await expect(app.locator(id)).not.toHaveClass(/open/);
    }
  });
});
