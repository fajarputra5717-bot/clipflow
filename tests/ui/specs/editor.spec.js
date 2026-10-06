// Editor page (lane B, P4 task 1: hook title card). Mock mode: /api/jobs/{j}/candidates/{c}/editor answered here.
const { test, expect } = require("../fixtures");

function editorState(over = {}) {
  return {
    job: { id: "job-done", title: "Mock finished stream", platform: "youtube_shorts", campaign: null, status: "review" },
    candidate: { id: "cand-a", status: "review", title: "First mock clip", reason: "Strong hook.", duration: 34,
                 has_preview: false, has_final: false, preview_url: "/api/jobs/job-done/candidates/cand-a/preview",
                 updated_at: "2026-10-05T10:00:00+00:00", edit_spec: {} },
    hook_title: { on: false, text: "", duration: 2.5, default_text: "First mock clip", durations: [2, 2.5, 3], max_chars: 80 },
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
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor(\/hook-title)?(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.method() === "PUT") {
      const body = req.postDataJSON();
      api.calls.push({ method: "PUT", path: new URL(req.url()).pathname, body });
      api.editor.hook_title = { ...api.editor.hook_title, ...body };
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api.editor) });
  });
}

test.describe("Editor timeline", () => {
  test("ruler, waveform and one chip per word, positioned by time", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const chips = app.locator(".ed-word");
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
    await expect(app.locator(".ed-word")).toHaveCount(3);
    await expect(app.locator("#edTl")).toContainText("waveform appears after the next Render preview");
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
