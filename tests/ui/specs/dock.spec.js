// UI phase 1 item 2: the dock. Equal icon buttons (48 px desktop / 44 phone, 24 px icons), a glider that slides under
// the active step (transform only), page-name tooltips on hover + keyboard focus, bar → pill on scroll with hysteresis,
// liquid glass with solid fallbacks, no motion with reduced motion. DOCK_SHOTS=<dir> also saves screenshots.
const { test, expect, job } = require("../fixtures");
const SHOTS = process.env.DOCK_SHOTS;

const gliderOffset = (app) => app.evaluate(() => {
  const g = document.getElementById("dockGlider").getBoundingClientRect(), b = document.querySelector("#flow li.active .flow-node").getBoundingClientRect();
  return Math.round(Math.abs(g.left - b.left) + Math.abs(g.top - b.top));
});
async function tall(app, api) {   // a page long enough to scroll
  api.current = Array.from({ length: 14 }, (_, i) => job({ id: "j" + i, status: "review", source_title: "Stream " + i }));
  api.jobs = { ...api.jobs, ...Object.fromEntries(api.current.map((j) => [j.id, j])) };
  await app.reload();
  await app.evaluate(() => window.showTab("current"));
}

test("glider sits under the active step and follows page switches", async ({ app }) => {
  await expect.poll(() => gliderOffset(app)).toBeLessThanOrEqual(1);
  for (const nav of ["schedule", "publish", "campaign", "current"]) {
    await app.locator(`#flow [data-nav="${nav}"]`).click();
    await expect.poll(() => gliderOffset(app), { timeout: 3000 }).toBeLessThanOrEqual(1);
  }
  const [bw, bh, icon] = await app.evaluate(() => {
    const b = document.querySelector("#flow .flow-node").getBoundingClientRect();
    return [Math.round(b.width), Math.round(b.height), Math.round(document.querySelector("#flow .flow-dot svg").getBoundingClientRect().width)];
  });
  expect([bw, bh, icon]).toEqual(test.info().project.name === "mobile" ? [44, 44, 24] : [48, 48, 24]);
  const moving = await app.evaluate(() => getComputedStyle(document.getElementById("dockGlider")).transitionProperty);
  expect(moving).not.toMatch(/left|width|top/);                      // transform + opacity only
});

test("bar → pill on scroll, with hysteresis", async ({ app, api }) => {
  await tall(app, api);
  await app.setViewportSize({ width: app.viewportSize().width, height: 600 });
  const pill = () => app.evaluate(() => document.getElementById("flowNav").classList.contains("is-pill"));
  expect(await pill()).toBe(false);
  if (SHOTS) await app.screenshot({ path: `${SHOTS}/dock-bar-${test.info().project.name}.png` });
  await app.evaluate(() => scrollTo(0, 40)); await app.waitForTimeout(100);
  expect(await pill()).toBe(false);                                   // < 64: still the bar
  await app.evaluate(() => scrollTo(0, 120)); await expect.poll(pill).toBe(true);
  if (SHOTS) { await app.waitForTimeout(500); await app.screenshot({ path: `${SHOTS}/dock-pill-${test.info().project.name}.png` }); }
  await app.evaluate(() => scrollTo(0, 40)); await app.waitForTimeout(100);
  expect(await pill()).toBe(true);                                    // hysteresis: stays a pill until < 24
  await app.evaluate(() => scrollTo(0, 0)); await expect.poll(pill).toBe(false);
});

test("tooltips name the page on hover and keyboard focus (desktop)", async ({ app }) => {
  test.skip(test.info().project.name === "mobile", "no hover on phones; the page title names the page");
  const tip = (nav) => app.locator(`#flow [data-nav="${nav}"] .flow-label`);
  expect(await tip("schedule").evaluate((e) => getComputedStyle(e).opacity)).toBe("0");
  await app.locator('#flow [data-nav="schedule"]').hover();
  await expect.poll(() => tip("schedule").evaluate((e) => getComputedStyle(e).opacity)).toBe("1");
  await expect(tip("schedule")).toHaveText("Schedule");
  if (SHOTS) { const r = await app.locator("#flowNav").boundingBox();
    await app.screenshot({ path: `${SHOTS}/dock-tooltip-desktop.png`, clip: { x: r.x - 30, y: r.y - 70, width: r.width + 60, height: r.height + 90 } }); }
  await app.mouse.move(5, 5);
  await app.locator('#flow [data-nav="publish"]').focus();
  await app.keyboard.press("Shift+Tab"); await app.keyboard.press("Tab");   // :focus-visible
  await expect.poll(() => tip("publish").evaluate((e) => getComputedStyle(e).opacity)).toBe("1");
});

test("glass with solid fallbacks; reduced motion = no transitions", async ({ app, browser }) => {
  const css = await app.evaluate(() => [...document.styleSheets].flatMap((s) => { try { return [...s.cssRules].map((r) => r.cssText); } catch { return []; } }).join("\n"));
  expect(css).toMatch(/prefers-reduced-transparency: reduce/);
  expect(css).toMatch(/@supports not/);
  const glass = await app.evaluate(() => getComputedStyle(document.getElementById("flowNav"), "::before").backdropFilter);
  expect(glass).toMatch(/blur/);
  await app.emulateMedia({ reducedMotion: "reduce" });
  expect(await app.evaluate(() => getComputedStyle(document.getElementById("dockGlider")).transitionDuration)).toMatch(/^0s/);
  if (SHOTS) for (const theme of ["light", "dark"]) {
    await app.evaluate((t) => window.applyTheme(t), theme);
    await app.waitForTimeout(200);
    const r = await app.locator("#flowNav").boundingBox();
    await app.screenshot({ path: `${SHOTS}/dock-${theme}-${test.info().project.name}.png`, clip: { x: Math.max(0, r.x - 30), y: r.y - 60, width: Math.min(r.width + 60, app.viewportSize().width), height: r.height + 80 } });
  }
});

// Frame budget (owner: 0 dropped frames on scroll and page switch at 1280 and 390; Lane C re-tests on real hardware).
// Here: rAF intervals > 25 ms (= a missed 60 Hz frame) while the dock animates, reported per run.
async function frames(app, action) {
  await app.evaluate(() => { window.__f = []; let t = performance.now(); const tick = (n) => { window.__f.push(n - t); t = n; if (window.__f.length < 400) window.__fid = requestAnimationFrame(tick); }; window.__fid = requestAnimationFrame(tick); });
  await action();
  return app.evaluate(() => { cancelAnimationFrame(window.__fid); const f = window.__f.slice(2); return { frames: f.length, slow: f.filter((d) => d > 25).length, worst: Math.round(Math.max(...f)) }; });
}
test("frames: scroll (bar → pill) and page switches", async ({ app, api }) => {
  test.skip(!process.env.DOCK_FRAMES, "timing test: run alone with DOCK_FRAMES=1 (parallel runs starve the CPU)");
  await tall(app, api);
  const scroll = await frames(app, async () => {
    for (let y = 0; y <= 600; y += 20) { await app.evaluate((v) => scrollTo(0, v), y); await app.waitForTimeout(16); }
    for (let y = 600; y >= 0; y -= 20) { await app.evaluate((v) => scrollTo(0, v), y); await app.waitForTimeout(16); }
  });
  const sw = await frames(app, async () => {
    for (const nav of ["schedule", "publish", "track", "current"]) { await app.locator(`#flow [data-nav="${nav}"]`).click(); await app.waitForTimeout(500); }
  });
  console.log(`FRAMES ${test.info().project.name} scroll ${JSON.stringify(scroll)} switch ${JSON.stringify(sw)}`);
  // Headless Chromium renders in software here: main itself drops ~24 frames in this desktop scroll (2026-10-14), the
  // dock 14–23 after blurring only the visible glass layer; phones 0. Guards against regressions; real GPUs: Lane C.
  const phone = test.info().project.name === "mobile";
  expect(scroll.slow).toBeLessThanOrEqual(phone ? 2 : 40);
  expect(sw.slow).toBeLessThanOrEqual(phone ? 2 : 25);
});
