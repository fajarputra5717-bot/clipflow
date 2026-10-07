// Editor page (lane B, P4 task 1: hook title card). Mock mode: /api/jobs/{j}/candidates/{c}/editor answered here.
const { test, expect } = require("../fixtures");

function editorState(over = {}) {
  return {
    job: { id: "job-done", title: "Mock finished stream", platform: "youtube_shorts", campaign: null, status: "review" },
    candidate: { id: "cand-a", status: "review", title: "First mock clip", reason: "Strong hook.", duration: 34,
                 has_preview: false, has_final: false, preview_url: "/api/jobs/job-done/candidates/cand-a/preview",
                 updated_at: "2026-10-05T10:00:00+00:00", edit_spec: {} },
    hook_title: { on: false, text: "", duration: 2.5, default_text: "First mock clip", durations: [2, 2.5, 3], max_chars: 80 },
    cuts: { trim: null, removed: [], output_seconds: 6, suggest_min_gap: 0.6, pad: 0.12 },
    zoom: { on: true, intensity: 50, markers: [], max_markers: 40 },
    ...over,
  };
}

const TIMELINE = {
  version: 1, duration: 6, rate: 50, cached: true,
  peaks: Array.from({ length: 300 }, (_, i) => Math.abs(Math.sin(i / 9))),
  words: [{ i: 0, text: "Hahahaha", start: 0, end: 0.4 }, { i: 1, text: "Kekuatan", start: 0.5, end: 1.1 },
          { i: 2, text: "hitam", start: 3.0, end: 3.5 }],
  gaps: [{ start: 1.1, end: 3.0 }],
};

async function mockEditor(page, api, timeline = TIMELINE) {
  api.editor = editorState();
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor\/timeline/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(timeline) }));
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor(\/hook-title|\/cuts|\/zoom)?(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.method() === "PUT") {
      const body = req.postDataJSON(), path = new URL(req.url()).pathname;
      api.calls.push({ method: "PUT", path, body });
      if (path.endsWith("/cuts")) api.editor.cuts = { ...api.editor.cuts, trim: body.trim, removed: body.removed };
      else if (path.endsWith("/zoom")) api.editor.zoom = { ...api.editor.zoom, ...body };
      else api.editor.hook_title = { ...api.editor.hook_title, ...body };
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api.editor) });
  });
}

test.describe("Editor timeline", () => {
  test("ruler, waveform and one chip per word, positioned by time", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const chips = app.locator("[data-ed-word]");
    await expect(chips).toHaveCount(3);
    await expect(chips.nth(2)).toHaveText("hitam");
    const left = await chips.nth(2).evaluate((el) => parseFloat(el.style.left));
    const inner = await app.locator("#edTlInner").evaluate((el) => parseFloat(el.style.width));
    expect(left / inner).toBeCloseTo(3.0 / 6, 2);                   // chip at 3.0 s of a 6 s clip
    expect(await app.locator("#edWave").evaluate((c) => c.width > 0)).toBe(true);
    await expect(app.locator("#edTl")).not.toContainText("waveform appears");
  });

  test("without a cached waveform: chips + a hint, no crash", async ({ app, api }) => {
    await mockEditor(app, api, { ...TIMELINE, peaks: null, cached: false });
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator("[data-ed-word]")).toHaveCount(3);
    await expect(app.locator("#edTl")).toContainText("waveform appears after the next Render preview");
  });
});

test.describe("Editor cuts", () => {
  const lastCuts = (api) => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/cuts")).at(-1)?.body;

  test("cut mode: click a word to strike it, again to restore; readout follows", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator("#edOut")).toHaveText("Output 6.0 s");
    await app.locator('[data-ed-mode="cut"]').click();
    const w = app.locator('[data-ed-word="1"]');                    // "Kekuatan" 0.5–1.1
    await w.click();
    await expect(w).toHaveClass(/cut/);
    await expect(app.locator("#edOut")).toHaveText("Output 5.4 s");
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [[0.5, 1.1]] });
    await w.click();
    await expect(w).not.toHaveClass(/cut/);
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [] });
  });

  test("seek mode clicks don't cut; C toggles the mode", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-word="1"]').click();
    await expect(app.locator('[data-ed-word="1"]')).not.toHaveClass(/cut/);
    await app.keyboard.press("c");
    await expect(app.locator('[data-ed-mode="cut"]')).toHaveAttribute("aria-pressed", "true");
  });

  test("suggested pauses (≥ 0.6 s) cut in one click, padded 0.12 s each side", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const btn = app.locator("[data-ed-suggest]");
    await expect(btn).toHaveText("Cut 1 pause ≥ 0.6 s");
    await btn.click();
    await expect(app.locator('[data-ed-pause="0"]')).toHaveClass(/cut/);
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [[1.22, 2.88]] });
    await expect(btn).toBeDisabled();
    await app.locator("[data-ed-cuts-reset]").click();
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [] });
  });

  test("trim handle: arrow keys move the start, Shift = 1 s", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const h = app.locator("#edTrimA");
    await h.focus();
    await app.keyboard.press("Shift+ArrowRight");
    await expect(h).toHaveAttribute("aria-valuenow", "1.0");
    await expect(app.locator('[data-ed-word="0"]')).toHaveClass(/cut/);   // "Hahahaha" 0–0.4 is outside
    await expect(app.locator("#edOut")).toHaveText("Output 5.0 s");
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: [1, 6], removed: [] });
  });
});

test.describe("Editor filler suggestions", () => {
  const FILLERS_TL = { ...TIMELINE,
    words: [...TIMELINE.words, { i: 3, text: "you", start: 4.0, end: 4.2 }, { i: 4, text: "know", start: 4.2, end: 4.5 },
            { i: 5, text: "eh", start: 5.0, end: 5.3 }],
    fillers: [{ i0: 3, i1: 4, start: 4.0, end: 4.5, text: "you know" }, { i0: 5, i1: 5, start: 5.0, end: 5.3, text: "eh" }] };
  const lastCuts = (api) => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/cuts")).at(-1)?.body;

  test("fillers show pre-struck as suggestions, nothing is cut until accepted", async ({ app, api }) => {
    await mockEditor(app, api, FILLERS_TL);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator('[data-ed-word="3"]')).toHaveClass(/filler-suggest/);
    await expect(app.locator('[data-ed-word="5"]')).toHaveClass(/filler-suggest/);
    await expect(app.locator('[data-ed-word="5"]')).not.toHaveClass(/\bcut\b/);
    await expect(app.locator("#edOut")).toHaveText("Output 6.0 s");
    await app.waitForTimeout(800);
    expect(api.calls.some((c) => c.method === "PUT")).toBe(false);          // never auto-cut
    await expect(app.locator("[data-ed-fillers]")).toHaveText("Cut 2 fillers");
  });

  test("Cut fillers accepts all; Restore all brings them back", async ({ app, api }) => {
    await mockEditor(app, api, FILLERS_TL);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator("[data-ed-fillers]").click();
    await expect(app.locator('[data-ed-word="4"]')).toHaveClass(/\bcut\b/);
    await expect(app.locator('[data-ed-word="4"]')).not.toHaveClass(/filler-suggest/);
    await expect(app.locator("#edOut")).toHaveText("Output 5.2 s");
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [[4, 4.5], [5, 5.3]] });
    await expect(app.locator("[data-ed-fillers]")).toBeDisabled();
    await app.locator("[data-ed-cuts-reset]").click();
    await expect(app.locator('[data-ed-word="5"]')).toHaveClass(/filler-suggest/);
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [] });
  });

  test("in cut mode, clicking one word of a multi-word filler cuts the whole filler", async ({ app, api }) => {
    await mockEditor(app, api, FILLERS_TL);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-mode="cut"]').click();
    await app.locator('[data-ed-word="4"]').click();
    await expect.poll(() => lastCuts(api), { timeout: 4000 }).toEqual({ trim: null, removed: [[4, 4.5]] });
  });
});

test.describe("Editor zoom punch-ins", () => {
  const lastZoom = (api) => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/zoom")).at(-1)?.body;

  test("zoom mode: click the timeline to add a punch-in, click the ◆ to remove it", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-mode="zoom"]').click();
    const inner = app.locator("#edTlInner");
    const box = await inner.boundingBox();
    await app.locator("#edTlScroll").evaluate((s) => { s.scrollLeft = 0; });
    await inner.click({ position: { x: 200, y: 50 } });                 // 2.0 s at 100 px/s
    await expect(app.locator("[data-ed-zoom-mark]")).toHaveCount(1);
    await expect.poll(() => lastZoom(api), { timeout: 4000 }).toEqual({ on: true, intensity: 50, markers: [2] });
    await app.locator("[data-ed-zoom-mark]").first().click();
    await expect(app.locator("[data-ed-zoom-mark]")).toHaveCount(0);
    await expect.poll(() => lastZoom(api), { timeout: 4000 }).toEqual({ on: true, intensity: 50, markers: [] });
    expect(box.width).toBeGreaterThan(0);
  });

  test("Z toggles zoom mode; a click on a word in zoom mode adds a marker instead of seeking", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.keyboard.press("z");
    await expect(app.locator('[data-ed-mode="zoom"]')).toHaveAttribute("aria-pressed", "true");
    await app.locator('[data-ed-word="2"]').click();                     // "hitam" 3.0–3.5
    await expect(app.locator("[data-ed-zoom-mark]")).toHaveCount(1);
    await expect.poll(() => lastZoom(api)?.markers?.[0], { timeout: 4000 }).toBeGreaterThan(2.9);
  });
});

test.describe("Editor page", () => {
  test("Open editor from Review shows the editor as its own view", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.locator('[data-nav="queue"]:visible').first().click();
    await app.locator('[data-queue-open="job-done"]').click();
    await app.locator('#candidate-cand-a [data-open-editor]').click();
    await expect(app.locator("#editorSection")).toBeVisible();
    await expect(app.locator("#pageTitle")).toHaveText("Editor");
    await expect(app.locator(".ed-title")).toHaveText("First mock clip");
    await expect(app.locator("#queueSection")).toBeHidden();
    await app.locator("[data-ed-back]").click();
    await expect(app.locator("#editorSection")).toBeHidden();
  });

  test("hook title card: toggle, text, duration are saved", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const sw = app.locator("[data-ed-hook-on]");
    await expect(sw).toHaveAttribute("aria-checked", "false");
    await sw.click();
    await expect(sw).toHaveAttribute("aria-checked", "true");
    await expect(app.locator("#edHookText")).toHaveAttribute("placeholder", "First mock clip");
    await app.locator("#edHookText").fill("Day 1 di Server RP");
    await app.locator('[data-ed-hook-dur="3"]').click();
    await expect(app.locator('[data-ed-hook-dur="3"]')).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT").at(-1)?.body, { timeout: 4000 })
      .toEqual({ on: true, text: "Day 1 di Server RP", duration: 3 });
    await expect(app.locator("#edState")).toContainText("not rendered yet");
  });

  test("Render preview saves first, then queues the existing preview render", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator("[data-ed-hook-on]").click();
    await app.locator("[data-ed-render]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path.endsWith("/regenerate-preview"))).toBe(true);
    const put = api.calls.findIndex((c) => c.method === "PUT");
    const post = api.calls.findIndex((c) => c.method === "POST" && c.path.endsWith("/regenerate-preview"));
    expect(put).toBeGreaterThanOrEqual(0);
    expect(put).toBeLessThan(post);
  });
});
