// 208 (owner bug): the island's "+N" opens a live list of every active task: mouse (it used to vanish under the
// pointer: hover-expand swallowed it), touch and keyboard; aria-expanded; Esc / outside click close it; the pill opens
// the list when several run and the task itself when one runs.
const { test, expect, job } = require("../fixtures");
const SHOTS = process.env.ISL_SHOTS;
const SIZES = { desktop: [1440, 900], mobile: [390, 844] };

async function start(app, api, n) {
  const [w, h] = SIZES[test.info().project.name];
  await app.setViewportSize({ width: w, height: h });
  const names = ["SEHARUSNYA GA GINI", "Second stream", "Third stream", "Fourth stream"];
  const stats = ["downloading", "analyzing", "transcribing", "analyzing"];
  api.current = names.slice(0, n).map((t, i) => job({ id: "r" + i, status: stats[i], progress: 10 + 20 * i, source_title: t }));
  api.jobs = { ...api.jobs, ...Object.fromEntries(api.current.map((j) => [j.id, j])) };
  await app.reload();
  return w;
}
const more = (app) => app.locator("#islandMore");
const list = (app) => app.locator("#jobOverlay");

for (const n of [2, 3]) {
  test(`${n} jobs: +${n - 1} opens a list of all ${n}, by pointer`, async ({ app, api }) => {
    const w = await start(app, api, n);
    await expect(more(app)).toBeVisible({ timeout: 8_000 });
    await expect(more(app)).toHaveText(`+${n - 1}`);
    await expect(more(app)).toHaveAttribute("aria-expanded", "false");
    const box = await more(app).boundingBox();
    if (test.info().project.name === "desktop") {
      await app.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 8 });   // a real pointer travels
      await app.waitForTimeout(500);
      await expect(more(app), "+N must not vanish under the pointer").toBeVisible();
      await app.mouse.down(); await app.mouse.up();
    } else await more(app).tap();
    await expect(list(app)).toHaveClass(/open/);
    await expect(more(app)).toHaveAttribute("aria-expanded", "true");
    const rows = app.locator("#jobOverlayList .running-job-item");
    await expect(rows).toHaveCount(n);
    await expect(rows.first().locator(".running-job-name")).toHaveText("SEHARUSNYA GA GINI");
    await expect(rows.first().locator(".running-job-stage")).toHaveText("Downloading");
    await expect(rows.nth(1).locator(".running-job-stage")).toHaveText("Analyzing");
    await expect(rows.first()).toHaveAttribute("aria-label", /SEHARUSNYA GA GINI: Downloading, 10%\. Open/);
    await expect(app.locator("#islandMain"), "a hover-expanded island must not cover the list").toHaveAttribute("aria-expanded", "false");
    if (SHOTS) { await app.waitForTimeout(700); await app.screenshot({ path: `${SHOTS}/after-${n}jobs-${w}.png` }); }
    await app.mouse.click(5, (SIZES[test.info().project.name][1]) - 200);   // outside
    await expect(list(app)).not.toHaveClass(/open/);
    await expect(more(app)).toHaveAttribute("aria-expanded", "false");
  });
}

test("keyboard: Enter on +N opens the list with focus on the first job, Esc closes and returns focus", async ({ app, api }) => {
  await start(app, api, 3);
  await expect(more(app)).toBeVisible({ timeout: 8_000 });
  await more(app).focus();
  await app.keyboard.press("Enter");
  await expect(list(app)).toHaveClass(/open/);
  await expect(app.locator("#jobOverlayList .running-job-item").first()).toBeFocused();
  await app.keyboard.press("Escape");
  await expect(list(app)).not.toHaveClass(/open/);
  await expect(more(app)).toBeFocused();
  await app.keyboard.press(" ");                                   // Space toggles too
  await expect(list(app)).toHaveClass(/open/);
});

test("the pill opens the list when several run; the list updates live and closes when the last finishes", async ({ app, api }) => {
  await start(app, api, 2);
  await expect(more(app)).toBeVisible({ timeout: 8_000 });
  await app.locator("#islandMain").click();
  await expect(list(app)).toHaveClass(/open/);
  const rows = app.locator("#jobOverlayList .running-job-item");
  await expect(rows).toHaveCount(2);
  api.current = [...api.current, job({ id: "r9", status: "analyzing", progress: 5, source_title: "Late arrival" })];
  api.jobs = { ...api.jobs, r9: api.current[2] };
  await expect(rows).toHaveCount(3, { timeout: 10_000 });
  await expect(rows.nth(2).locator(".running-job-name")).toHaveText("Late arrival");
  api.current = api.current.slice(1);
  await expect(rows).toHaveCount(2, { timeout: 10_000 });
  api.current = [];
  await expect(list(app)).not.toHaveClass(/open/, { timeout: 10_000 });
});

test("one job: no +N, the pill opens that job", async ({ app, api }) => {
  await start(app, api, 1);
  await expect(app.locator("#islandMain")).toBeVisible({ timeout: 8_000 });
  await app.evaluate(() => { location.hash = "#import"; });
  await expect(more(app)).toBeHidden();
  await app.locator("#islandMain").click();
  await expect(list(app)).not.toHaveClass(/open/);
  await expect(app.locator("#pageTitle")).toHaveText("Analyze");
});
