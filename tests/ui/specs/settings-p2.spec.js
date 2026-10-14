// UI phase 2, Settings (owner 2026-10-14): sections with a side menu (Posting, Sounds, Watermarks, System; tabs on
// phones), search across every section, the platform select never truncated, "Reload" → "Discard changes".
const { test, expect, settingsSection } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

async function open(app, api) {
  const g = (value, scope = "global") => ({ value, configured: true, source: "default", scope });
  api.settings = { GEMINI_ANALYSIS_MODEL: g("gemini-3.6-flash"), WATERMARK_WIDTH: g("300", "user"), HASHTAGS: g("", "user"), CLIPS_PER_JOB: g("4", "user") };
  await app.reload();
  await app.waitForResponse((r) => r.url().includes("/api/settings"));
  if (!(await app.locator('#toolbar .icon-btn[data-nav="settings"]').isVisible())) await app.click("#accountMenuBtn");
  await app.locator('[data-nav="settings"] >> visible=true').first().click();
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
}

test("side menu: one section at a time; search covers every section", async ({ app, api }) => {
  await open(app, api);
  const nav = app.locator("[data-settings-nav]");
  await expect(nav).toHaveText(["Posting", "Sounds", "Watermarks", "System"]);
  await expect(app.locator('[data-settings-nav="posting"]')).toHaveAttribute("aria-current", "true");
  await expect(app.locator("#accountsAdmin")).toBeVisible();
  await expect(app.locator("#set-WATERMARK_WIDTH")).toBeHidden();
  await settingsSection(app, "watermarks");
  await expect(app.locator("#set-WATERMARK_WIDTH")).toBeVisible();
  await expect(app.locator("#accountsAdmin")).toBeHidden();
  await expect(app.locator('[data-settings-nav="watermarks"]')).toHaveAttribute("aria-current", "true");
  await settingsSection(app, "sounds");
  await expect(app.locator("[data-open-sfx]")).toBeVisible();
  await settingsSection(app, "system");
  await expect(app.locator("#set-GEMINI_ANALYSIS_MODEL")).toBeVisible();
  await app.fill("#settingsSearch", "hashtags");                                 // search: every section
  await expect(app.locator("#set-HASHTAGS")).toBeVisible();
  await expect(app.locator('[data-settings-nav][aria-current="true"]')).toHaveCount(0);
  await app.fill("#settingsSearch", "");
  await expect(app.locator('[data-settings-nav="system"]')).toHaveAttribute("aria-current", "true");
  if (process.env.P2_SHOTS) await app.screenshot({ path: `${process.env.P2_SHOTS}/settings-${test.info().project.name}.png` });
});

test("platform select shows its whole label; Discard changes only with changes", async ({ app, api }) => {
  await open(app, api);
  const sel = app.locator("#newAccountPlatform");
  await expect(sel).toBeVisible();
  const fits = await sel.evaluate((s) => { const c = document.createElement("canvas").getContext("2d"); c.font = getComputedStyle(s).font;
    const widest = Math.max(...[...s.options].map((o) => c.measureText(o.text).width)); return s.clientWidth >= widest + 24; });
  expect(fits).toBe(true);
  const discard = app.locator("#reloadSettings");
  await expect(discard).toHaveText("Discard changes");
  await expect(discard).toBeDisabled();
  await settingsSection(app, "watermarks");
  await app.fill("#set-WATERMARK_WIDTH", "420");
  await expect(discard).toBeEnabled();
  await discard.click();
  await expect(app.locator("#set-WATERMARK_WIDTH")).toHaveValue("300");
  await expect(discard).toBeDisabled();
});

test("the selected section reads clearly in both themes", async ({ app, api }) => {
  await open(app, api);
  for (const theme of ["light", "dark"]) {
    await app.evaluate((t) => window.applyTheme(t), theme);
    await settingsSection(app, "system");
    const [fg, bg] = await app.locator('[data-settings-nav="system"]').evaluate((e) => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]);
    expect(fg, theme).not.toBe(bg);
    const accent = await app.evaluate(() => { const i = document.createElement("i"); i.style.color = "var(--accent)"; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; });
    expect(bg, `${theme}: not a solid accent pill`).not.toBe(accent);
  }
});
