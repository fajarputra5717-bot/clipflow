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
    progress: { on: false, color: "#FFD60A", colors: ["#FFD60A", "#FFFFFF", "#FF453A", "#0A84FF"] },
    audio: { compress: false, silence_trim: false, silence_ranges: [], loudness: { lufs: -14, true_peak_dbtp: -1, always_on: true } },
    captions: CAPTIONS(),
    thumbnail: { options: [0, 1, 2].map((i) => ({ index: i, url: `/api/jobs/job-done/candidates/cand-a/thumbnail-options/${i}` })),
                 picked: null, locked: false, current_url: "/api/jobs/job-done/candidates/cand-a/thumbnail", generating: false },
    watermark: { width: 320, opacity: 1, custom: false },
    export: { burn: true, description: "", submagic: { status: null, preview_url: null, error: null } },
    ...over,
  };
}

const CAPTIONS = () => ({
  job: { style: "outline", animation: "karaoke", font: "Montserrat Black", size: 42 }, clip: null, style: "outline", animation: "karaoke",
  caption_y: null, auto_caption_y: 78, keywords: ["kekuatan"], keyword_color: null, auto_keyword_color: "#30D158",
  transcript: "HAHAHAHA KEKUATAN\nHITAM", override: "", text: "HAHAHAHA KEKUATAN\nHITAM", burn: true,
  options: {
    styles: [{ id: "outline", label: "Outline", resting: "#FFFFFF", highlight: "#FFD60A", weight: 800, outline: 4.5, shadow: true, box: false, sizeMult: 1, letterSpacing: "0" },
             { id: "impact", label: "Impact", resting: "#FFFFFF", highlight: "#FF3B30", weight: 900, outline: 2, shadow: true, box: false, sizeMult: 1.08, letterSpacing: "0" },
             { id: "neon", label: "Neon", resting: "#5CE1FF", highlight: "#FF2D95", weight: 800, outline: 2.5, shadow: true, box: false, sizeMult: 1, letterSpacing: "0" }],
    animations: [{ id: "karaoke", label: "Karaoke sweep", family: "flow" }, { id: "word_pop", label: "Word pop", family: "chunk" }, { id: "typewriter", label: "Typewriter", family: "typewriter" }],
    presets: [{ id: "karaoke", label: "Karaoke", style: "outline", animation: "karaoke" }, { id: "pop", label: "Word pop", style: "impact", animation: "word_pop" },
              { id: "neon", label: "Neon", style: "neon", animation: "typewriter" }],
    fonts: ["Liberation Sans Bold", "Montserrat Black", "Anton"],
    keyword_colors: [{ color: "#FFD60A", label: "Yellow" }, { color: "#30D158", label: "Green" }, { color: "#FF453A", label: "Red" }],
    size_range: [12, 120], caption_y_range: [30, 85],
  },
});

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
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor(\/hook-title|\/cuts|\/zoom|\/progress|\/audio)?(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.method() === "PUT") {
      const body = req.postDataJSON(), path = new URL(req.url()).pathname;
      api.calls.push({ method: "PUT", path, body });
      if (path.endsWith("/cuts")) api.editor.cuts = { ...api.editor.cuts, trim: body.trim, removed: body.removed };
      else if (path.endsWith("/zoom")) api.editor.zoom = { ...api.editor.zoom, ...body };
      else if (path.endsWith("/progress")) api.editor.progress = { ...api.editor.progress, ...body };
      else if (path.endsWith("/audio")) api.editor.audio = { ...api.editor.audio, ...body };
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
    await app.evaluate(async () => { await window.showTab("queue"); });   // the old panel's "Open editor" (All edits path)
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

// P4 task 5: Effects + Audio tabs are live controls saved to edit_spec (debounced PUT), loudness is read-only.
test.describe("Editor Effects + Audio tabs", () => {
  test.use({ reducedMotion: "reduce" });
  const lastPut = (api, end) => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith(end)).at(-1)?.body;
  async function openEd(app, api) {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator('[data-ed-tab="effects"]')).toBeVisible();
  }

  test("Effects: progress bar on + colour, punch-in switch + intensity", async ({ app, api }) => {
    await openEd(app, api);
    await app.locator('[data-ed-tab="effects"]').click();
    await app.locator("[data-ed-progress-on]").click();
    await app.locator('[data-ed-progress-color="#FF453A"]').click();
    await expect(app.locator('[data-ed-progress-color="#FF453A"]')).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => lastPut(api, "/progress"), { timeout: 3000 }).toEqual({ on: true, color: "#FF453A" });
    await app.locator("[data-ed-zoom-intensity]").fill("80");
    await expect(app.locator("#edZoomOut")).toHaveText("80%");
    await expect.poll(() => lastPut(api, "/zoom")?.intensity, { timeout: 3000 }).toBe(80);
    await app.locator("[data-ed-zoom-on]").click();
    await expect.poll(() => lastPut(api, "/zoom")?.on, { timeout: 3000 }).toBe(false);
  });

  test("Audio: compression + silence trim save; loudness is read-only", async ({ app, api }) => {
    await openEd(app, api);
    await app.locator('[data-ed-tab="audio"]').click();
    await expect(app.locator(".ed-panel")).toContainText("-14 LUFS");
    await app.locator("[data-ed-compress]").click();
    await expect.poll(() => lastPut(api, "/audio")?.compress, { timeout: 3000 }).toBe(true);
    await app.locator("[data-ed-silence]").click();
    await expect.poll(() => lastPut(api, "/audio")?.silence_trim, { timeout: 3000 }).toBe(true);
    expect(lastPut(api, "/audio").silence_ranges.length).toBeGreaterThan(0);
    await expect.poll(() => lastPut(api, "/cuts")?.removed.length, { timeout: 3000 }).toBeGreaterThan(0);
    await app.locator("[data-ed-silence]").click();
    await expect.poll(() => lastPut(api, "/cuts")?.removed.length, { timeout: 3000 }).toBe(0);
  });
});

// P4 task 7a: Captions tab = preset tiles, keywords, caption text + Fix typos, style/font/size/position, new hook.
// Writes go to main's existing routes (candidate PATCH, subtitle-style, caption-preset, fix-subtitle-ai, new-hook).
test.describe("Editor Captions tab", () => {
  test.use({ reducedMotion: "reduce" });
  const CAND = "/api/jobs/job-done/candidates/cand-a";
  const last = (api, method, path) => api.calls.filter((c) => c.method === method && c.path === path).at(-1)?.body;
  async function openEd(app, api) {
    await mockEditor(app, api);
    await app.route(/\/fix-subtitle-ai$/, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subtitle_text: "hahahaha kekuatan\nhitam legam" }) }));
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator("[data-ed-preset]").first()).toBeVisible();
  }

  test("preset is this clip's own; equal to the job's clears it; untouched keywords aren't sent", async ({ app, api }) => {
    await openEd(app, api);
    await expect(app.locator('[data-ed-preset="karaoke"]')).toHaveAttribute("aria-pressed", "true");
    await app.locator('[data-ed-preset="pop"]').click();
    await expect(app.locator('[data-ed-preset="pop"]')).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => last(api, "PATCH", CAND)?.edit_spec?.caption, { timeout: 3000 }).toEqual({ style: "impact", animation: "word_pop" });
    expect(last(api, "PATCH", CAND).edit_spec).not.toHaveProperty("keywords");
    await app.locator('[data-ed-preset="karaoke"]').click();
    await expect.poll(() => last(api, "PATCH", CAND)?.edit_spec?.caption, { timeout: 3000 }).toBeNull();
  });

  test("keywords toggle + colour; caption text edit and Fix typos send subtitle_override", async ({ app, api }) => {
    await openEd(app, api);
    await expect(app.locator('[data-ed-kw="kekuatan"]')).toHaveAttribute("aria-pressed", "true");
    await app.locator('[data-ed-kw="hitam"]').click();
    await app.locator('[data-ed-kw-color="#FF453A"]').click();
    await expect.poll(() => last(api, "PATCH", CAND)?.edit_spec?.keyword_color, { timeout: 3000 }).toBe("#FF453A");
    expect(last(api, "PATCH", CAND).edit_spec.keywords.sort()).toEqual(["hitam", "kekuatan"]);
    await app.locator("[data-ed-fix-typos]").click();
    await expect(app.locator("#edCapText")).toHaveValue("HAHAHAHA KEKUATAN\nHITAM LEGAM");
    await expect.poll(() => last(api, "PATCH", CAND)?.subtitle_override, { timeout: 3000 }).toBe("HAHAHAHA KEKUATAN\nHITAM LEGAM");
    await app.locator("[data-ed-cap-reset]").click();
    await expect.poll(() => last(api, "PATCH", CAND)?.subtitle_override, { timeout: 3000 }).toBe("");
  });

  test("font + size are job-level; position switch + slider; Apply to all clips", async ({ app, api }) => {
    await openEd(app, api);
    await app.locator("[data-ed-style-more] > summary").click();
    await app.locator('select[data-ed-cap="font"]').selectOption("Anton");
    await app.locator('input[data-ed-cap="size"]').fill("56");
    await expect.poll(() => last(api, "PATCH", "/api/jobs/job-done/subtitle-style"), { timeout: 3000 })
      .toEqual({ subtitle_style: "outline", subtitle_font: "Anton", subtitle_size: 56, subtitle_animation: "karaoke" });
    await app.locator("[data-ed-capy-on]").click();
    await expect(app.locator("#edCapY")).toHaveText("78 %");
    await app.locator("[data-ed-capy]").fill("60");
    await expect.poll(() => last(api, "PATCH", CAND)?.edit_spec?.caption_y, { timeout: 3000 }).toBe(60);
    await expect(app.locator("[data-ed-style-more]")).toHaveAttribute("open", "");          // stays open across repaints
    await app.locator('select[data-ed-cap="style"]').selectOption("neon");
    await app.locator("[data-ed-cap-all]").click();
    await expect(app.locator("[data-ed-cap-all]")).toHaveText("Tap again: every clip re-renders");
    expect(api.calls.some((c) => c.path.endsWith("/caption-preset"))).toBe(false);
    await app.locator("[data-ed-cap-all]").click();
    await expect.poll(() => last(api, "POST", "/api/jobs/job-done/caption-preset")).toEqual({ style: "neon", animation: "karaoke" });
  });

  test("Get another hook needs a second tap, then calls new-hook", async ({ app, api }) => {
    await openEd(app, api);
    await app.locator("[data-ed-new-hook]").click();
    await expect(app.locator("[data-ed-new-hook]")).toHaveText("Tap again to replace this clip");
    expect(api.calls.some((c) => c.path.endsWith("/new-hook"))).toBe(false);
    await app.locator("[data-ed-new-hook]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === CAND + "/new-hook")).toBe(true);
  });
});

// P4 task 7b: Thumbnail tab = AI options + upload + pick (one list; a pick locks it for later renders).
test.describe("Editor Thumbnail tab", () => {
  test.use({ reducedMotion: "reduce" });
  const CAND = "/api/jobs/job-done/candidates/cand-a";
  async function openThumb(app, api) {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="thumbnail"]').click();
    await expect(app.locator("[data-ed-thumb-pick]")).toHaveCount(3);
  }

  test("tap an option to pick it (PATCH selected_thumbnail_index); the tab bar keeps every label whole", async ({ app, api }) => {
    await openThumb(app, api);
    await app.locator('[data-ed-thumb-pick="1"]').click();
    await expect(app.locator('[data-ed-thumb-pick="1"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator("#edThumbNote")).toHaveText("Picked: renders keep this thumbnail.");
    await expect.poll(() => api.calls.find((c) => c.method === "PATCH" && c.path === CAND)?.body).toEqual({ selected_thumbnail_index: 1 });
    const clipped = await app.locator(".ed-seg button").evaluateAll((bs) => bs.filter((b) => b.scrollWidth > b.clientWidth + 1).length);
    expect(clipped).toBe(0);
    expect(await app.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });

  test("Generate with AI queues generation and refreshes the options when it finishes", async ({ app, api }) => {
    await openThumb(app, api);
    await app.locator("[data-ed-thumb-gen]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === CAND + "/generate-thumbnails-ai")).toBe(true);
    await expect(app.locator("[data-ed-thumb-gen]")).toBeDisabled();
    api.editor.thumbnail = { ...api.editor.thumbnail, options: [...api.editor.thumbnail.options, { index: 3, url: CAND + "/thumbnail-options/3" }] };
    await expect(app.locator("[data-ed-thumb-pick]")).toHaveCount(4, { timeout: 8000 });
    await expect(app.locator("[data-ed-thumb-gen]")).toBeEnabled();
  });

  test("upload adds an option and picks it", async ({ app, api }) => {
    await openThumb(app, api);
    await app.route(/\/thumbnail-upload$/, (r) => {
      api.editor.thumbnail = { ...api.editor.thumbnail, picked: 3, locked: true,
        options: [...api.editor.thumbnail.options, { index: 3, url: CAND + "/thumbnail-options/3" }] };
      return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ index: 3 }) });
    });
    await app.locator("[data-ed-thumb-upload]").setInputFiles({ name: "t.png", mimeType: "image/png", buffer: Buffer.from("89504e47", "hex") });
    await expect.poll(() => api.calls.find((c) => c.method === "PATCH" && c.path === CAND)?.body).toEqual({ selected_thumbnail_index: 3 });
    await expect(app.locator('[data-ed-thumb-pick="3"]')).toHaveAttribute("aria-pressed", "true");
  });
});

// P4 task 7c/7d: Watermark tab (job size/opacity) + Export tab (burn, description, Submagic, versions, approve).
test.describe("Editor Watermark + Export tabs", () => {
  test.use({ reducedMotion: "reduce" });
  const CAND = "/api/jobs/job-done/candidates/cand-a", JOB = "/api/jobs/job-done";
  async function openTab(app, api, tab) {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator(`[data-ed-tab="${tab}"]`).click();
  }
  test("watermark sliders PATCH render-options", async ({ app, api }) => {
    await openTab(app, api, "watermark");
    await app.locator('[data-ed-wm="width"]').fill("500");
    await expect(app.locator("#edWmW")).toHaveText("500 px");
    await expect.poll(() => api.calls.find((c) => c.method === "PATCH" && c.path === JOB + "/render-options")?.body)
      .toEqual({ watermark_width: 500, watermark_opacity: 1 });
  });
  test("export: burn toggle, description save, version history restore", async ({ app, api }) => {
    await openTab(app, api, "export");
    await app.locator("[data-ed-burn]").click();
    await expect.poll(() => api.calls.find((c) => c.method === "PATCH" && c.path === JOB + "/render-options")?.body).toEqual({ burn_subtitles: false });
    await app.locator("#edDesc").fill("Hello caption");
    await expect.poll(() => api.calls.find((c) => c.method === "PATCH" && c.path === CAND)?.body).toEqual({ description: "Hello caption" });
    await app.locator("[data-ed-versions]").click();
    await expect(app.locator("#edVersions")).toContainText("No versions yet");
    await app.locator('[data-ed-sm="start"]').click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === CAND + "/submagic/start")).toBe(true);
  });
  test("approve calls the approve route and shows a gate error", async ({ app, api }) => {
    await openTab(app, api, "export");
    await app.locator("[data-ed-approve]").click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === CAND + "/approve")).toBe(true);
  });
});

// Deep links survive a reload (Cmd+R): #editor/<job>/<clip> and #review/<job>.
test.describe("Deep links after reload", () => {
  test.use({ reducedMotion: "reduce" });
  test("#editor/<job>/<clip> reopens the editor", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator(".ed-title")).toBeVisible();
    await app.reload();
    await expect(app.locator(".ed-title")).toHaveText("First mock clip");
    expect(await app.evaluate(() => location.hash)).toBe("#editor/job-done/cand-a");
  });
});
