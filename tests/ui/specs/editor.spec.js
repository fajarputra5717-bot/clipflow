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

async function mockEditor(page, api) {
  api.editor = editorState();
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor/, async (route) => {
    const req = route.request();
    if (req.method() === "PUT") {
      const body = req.postDataJSON();
      api.calls.push({ method: "PUT", path: new URL(req.url()).pathname, body });
      api.editor.hook_title = { ...api.editor.hook_title, ...body };
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api.editor) });
  });
}

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
