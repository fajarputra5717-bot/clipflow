// UI phase 2, Watermarks (owner 2026-10-14): the preview is the mark's visible pixels (alpha-cropped) on a sample 9:16
// frame at the Watermark width / height settings; rename (PATCH filename) and delete per tile.
const { test, expect } = require("../fixtures");
test.use({ reducedMotion: "reduce" });
// 40×20 PNG: transparent with an opaque 20×6 block in the middle
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACgAAAAUCAYAAAD/Rn+7AAAAJUlEQVR4nO3OQQ0AAAgEoOtfWjs453xAAhKAH2qZoKDgdRBgpgGyBd4wlSTOtgAAAABJRU5ErkJggg==", "base64");

async function open(app, api) {
  api.settings = { ...(api.settings || {}), WATERMARK_WIDTH: { value: "540", source: "default", scope: "user" }, WATERMARK_POSITION_Y: { value: "30", source: "default", scope: "user" } };
  const assets = [{ id: "wm-1", filename: "motionklip.png", width: 40, height: 20, active: true }, { id: "wm-2", filename: "old.png", width: 40, height: 20, active: false }];
  await app.route(/\/api\/assets\/watermarks(\?|$)/, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ active_id: "wm-1", assets }) }));
  await app.route(/\/api\/assets\/watermarks\/[^/]+\/file/, (r) => r.fulfill({ status: 200, contentType: "image/png", body: PNG }));
  await app.route(/\/api\/assets\/watermarks\/wm-1$/, (r) => {
    if (r.request().method() === "PATCH") { assets[0].filename = r.request().postDataJSON().filename; return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) }); }
    return r.fallback();
  });
  await app.reload();
  await app.waitForResponse((r) => r.url().includes("/api/settings"));
  if (!(await app.locator('#toolbar .icon-btn[data-nav="watermarks"]').isVisible())) await app.click("#accountMenuBtn");
  await app.locator('[data-nav="watermarks"] >> visible=true').first().click();
  await expect(app.locator("#watermarkSheet")).toHaveClass(/open/);
}

test("preview: cropped to the visible pixels, on a 9:16 sample frame at the width / height settings", async ({ app, api }) => {
  await open(app, api);
  const img = app.locator('img[data-wm-crop="wm-1"]');
  await expect.poll(() => img.evaluate((e) => e.src.startsWith("data:image/png"))).toBe(true);   // cropped in a canvas
  const [nw, nh] = await img.evaluate((e) => [e.naturalWidth, e.naturalHeight]);
  expect([nw, nh]).toEqual([20, 6]);                                           // the opaque block only
  const frame = app.locator('[data-wm-id="wm-1"] .wm-frame');
  const [f, i] = [await frame.boundingBox(), await img.boundingBox()];
  expect(Math.round((f.height / f.width) * 9)).toBe(16);                       // 9:16
  expect(i.width / f.width).toBeCloseTo(0.5, 1);                                // 540 of 1080
  expect((i.y + i.height / 2 - f.y) / f.height).toBeCloseTo(0.3, 1);           // centred at 30 %
  if (process.env.P2_SHOTS) await app.screenshot({ path: `${process.env.P2_SHOTS}/watermarks-${test.info().project.name}.png` });
});

test("rename (Enter saves, Esc cancels) and delete with Undo", async ({ app, api }) => {
  await open(app, api);
  await app.click('[data-watermark-rename="wm-1"]');
  const inp = app.locator(".wm-rename-input");
  await inp.fill("nope"); await inp.press("Escape");
  await expect(app.locator("#watermarkSheet")).toHaveClass(/open/);
  await expect(app.locator('[data-wm-id="wm-1"] .wm-name')).toHaveText("motionklip.png");
  await app.click('[data-watermark-rename="wm-1"]');
  await app.locator(".wm-rename-input").fill("Motion Klip 2026");
  await app.locator(".wm-rename-input").press("Enter");
  await expect(app.locator('[data-wm-id="wm-1"] .wm-name')).toHaveText("Motion Klip 2026");
  await expect(app.locator('[data-watermark-rename="wm-1"]')).toBeFocused();
  await app.click('[data-watermark-delete="wm-2"]');
  await expect(app.locator('[data-wm-id="wm-2"]')).toHaveCount(0);
  await app.click("#toastAction");
  await expect(app.locator('[data-wm-id="wm-2"]')).toHaveCount(1);
});
