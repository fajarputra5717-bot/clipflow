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
    audio: { compress: false, loud: false, silence_trim: false, silence_ranges: [], loudness: { lufs: -14, true_peak_dbtp: -1, always_on: true } },
    captions: CAPTIONS(),
    thumbnail: { options: [0, 1, 2].map((i) => ({ index: i, url: `/api/jobs/job-done/candidates/cand-a/thumbnail-options/${i}` })),
                 picked: null, locked: false, current_url: "/api/jobs/job-done/candidates/cand-a/thumbnail", generating: false },
    watermark: { width: 320, opacity: 1, custom: false },
    export: { burn: true, description: "", submagic: { status: null, preview_url: null, error: null } },
    director: { items: [], rendered: ["emoji", "flash", "freeze", "punch", "push", "shake", "slowmo", "whip", "zoom_out"], arrives_in: {}, min_gap: 3, frames_ready: false, vision_on: true,
      effects: ["punch", "push", "zoom_out", "shake", "flash", "whip", "freeze", "slowmo", "emoji"], defaults: { emoji: { emoji: "😂" }, freeze: { hold: 0.6 }, slowmo: { dur: 1.2, factor: 0.5 } },
      sfx: ["whoosh", "boom", "bass_hit", "ding", "record_scratch"], emoji: ["😂", "😭", "💀"] },
    look: { preset: "none", vignette: false, grain: false, presets: ["none", "vivid_gaming", "warm", "moody"] },
    pack: { id: "podcast_clean", name: "Podcast Clean", from_campaign: true, options: [{ id: "gaming_hype", name: "Gaming Hype", min_gap: 3 },
      { id: "funny_meme", name: "Funny / Meme", min_gap: 3 }, { id: "drama_tension", name: "Drama / Tension", min_gap: 5 }, { id: "podcast_clean", name: "Podcast Clean", min_gap: 6 }] },
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
  await page.route(/\/api\/jobs\/[^/]+\/candidates\/[^/]+\/editor(\/hook-title|\/cuts|\/zoom|\/progress|\/audio|\/plan|\/look|\/pack)?(\?.*)?$/, async (route) => {
    const req = route.request();
    if (req.method() === "PUT") {
      const body = req.postDataJSON(), path = new URL(req.url()).pathname;
      api.calls.push({ method: "PUT", path, body });
      if (path.endsWith("/cuts")) api.editor.cuts = { ...api.editor.cuts, trim: body.trim, removed: body.removed };
      else if (path.endsWith("/zoom")) api.editor.zoom = { ...api.editor.zoom, ...body };
      else if (path.endsWith("/progress")) api.editor.progress = { ...api.editor.progress, ...body };
      else if (path.endsWith("/audio")) api.editor.audio = { ...api.editor.audio, ...body };
      else if (path.endsWith("/plan")) api.editor.director = { ...api.editor.director, items: body.items };
      else if (path.endsWith("/look")) api.editor.look = { ...api.editor.look, ...body };
      else api.editor.hook_title = { ...api.editor.hook_title, ...body };
    }
    if (req.method() === "POST" && new URL(req.url()).pathname.endsWith("/pack")) {   // Auto Edit E5
      const body = req.postDataJSON();
      api.calls.push({ method: "POST", path: new URL(req.url()).pathname, body });
      api.editor.pack = { ...api.editor.pack, id: body.pack, name: "Gaming Hype", from_campaign: false };
      api.editor.look = { ...api.editor.look, preset: "vivid_gaming" };
    }
    if (req.method() === "POST" && new URL(req.url()).pathname.endsWith("/plan")) {   // Auto Edit E1
      api.calls.push({ method: "POST", path: new URL(req.url()).pathname });
      api.editor.director = { ...api.editor.director, vision: true, provider: "gemini", items: [
        { id: "punch-50", t: 0.5, effect: "punch", params: {}, reason: "punchline: kekuatan", source: "transcript", on: true },
        { id: "shake-350", t: 3.5, effect: "shake", params: {}, reason: "loud: loudness peak", source: "audio", on: true }] };
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
  test("layout: desktop fits the window (no page scroll, timeline docked, inspector scrolls); phone = video, timeline, inspector", async ({ app, api }, info) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator(".ed-tl-inner")).toBeVisible();
    const box = async (q) => app.locator(q).first().boundingBox();
    if (info.project.name === "desktop") {
      for (const [w, h] of [[1280, 800], [1440, 900]]) {
        await app.setViewportSize({ width: w, height: h });
        await expect.poll(() => app.evaluate(() => document.documentElement.scrollHeight - innerHeight)).toBeLessThanOrEqual(0);
        const tl = await box(".ed-tlwrap"), pill = await box("#flowNav"), foot = await box(".ed-foot"), frame = await box(".ed-frame");
        expect(tl.y + tl.height).toBeLessThanOrEqual(pill.y);                 // docked above the stepper, fully visible
        expect(foot.y).toBeGreaterThanOrEqual(frame.y + frame.height);        // action bar under the video, not over it
        expect(await app.locator(".ed-panel").evaluate((e) => getComputedStyle(e).overflowY)).toBe("auto");
      }
    } else {
      const player = await box(".ed-player"), tl = await box(".ed-tlwrap"), insp = await box(".ed-insp");
      expect(tl.y).toBeGreaterThanOrEqual(player.y + player.height - 1);
      expect(insp.y).toBeGreaterThan(tl.y);
    }
  });

  test("Split: line between video and timeline — default video 455 px when it fits, arrow keys + drag, remembered per user", async ({ app, api }, info) => {
    test.skip(info.project.name !== "desktop", "desktop fit layout only (the phone layout has no split)");
    await app.setViewportSize({ width: 1280, height: 900 });
    await app.evaluate(() => { try { Object.keys(localStorage).filter((k) => k.includes("editor_split")).forEach((k) => localStorage.removeItem(k)); } catch {} });
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    const split = app.locator("[data-ed-split]"), frameH = () => app.locator(".ed-frame").evaluate((e) => Math.round(e.getBoundingClientRect().height));
    const tlH = () => app.locator(".ed-tlwrap").evaluate((e) => Math.round(e.getBoundingClientRect().height));
    await expect(split).toBeVisible();
    await expect.poll(frameH).toBe(455);
    const v0 = Number(await split.getAttribute("aria-valuenow")), t0 = await tlH();
    await split.focus();
    await app.keyboard.press("ArrowUp");                               // line up: timeline +16, video −16
    await expect.poll(tlH).toBe(t0 + 16);
    expect(Number(await split.getAttribute("aria-valuenow"))).toBeLessThan(v0);
    await app.keyboard.press("Shift+ArrowDown");                       // −64
    await expect.poll(tlH).toBe(t0 - 48 < 72 ? 72 : t0 - 48);
    await app.keyboard.press("End");
    await expect.poll(tlH).toBe(72);                                   // never collapses
    await app.keyboard.press("Home");
    await expect.poll(frameH).toBe(200);                               // video keeps its minimum
    const box = await split.boundingBox();
    await app.mouse.move(box.x + box.width / 2, box.y + 6); await app.mouse.down();
    await app.mouse.move(box.x + box.width / 2, box.y + 106, { steps: 5 }); await app.mouse.up();
    const after = await tlH();
    expect(after).toBeLessThan(await app.evaluate(() => innerHeight));
    await app.evaluate(() => { location.hash = "#review/job-done"; });
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect.poll(tlH).toBe(after);                                // remembered
    expect(await app.evaluate(() => document.documentElement.scrollHeight - innerHeight)).toBeLessThanOrEqual(0);
  });

  test("Word chips: one Tab stop; ←/→ move in time order, Home/End jump; Tab leaves to the inspector side", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator(".ed-tl-words > button").first()).toBeVisible();
    const chips = app.locator(".ed-tl-words > button");
    const n = await chips.count();
    expect(await chips.evaluateAll((bs) => bs.filter((b) => b.tabIndex === 0).length)).toBe(1);
    const order = await chips.evaluateAll((bs) => bs.sort((a, b) => parseFloat(a.style.left) - parseFloat(b.style.left)).map((b) => b.textContent.trim()));
    const focused = () => app.evaluate(() => document.activeElement.textContent.trim());
    await app.locator('.ed-tl-words > button[tabindex="0"]').focus();
    expect(await focused()).toBe(order[0]);
    await app.keyboard.press("ArrowRight");
    expect(await focused()).toBe(order[1]);
    await app.keyboard.press("End");
    expect(await focused()).toBe(order[n - 1]);
    await app.keyboard.press("Home");
    expect(await focused()).toBe(order[0]);
    await app.keyboard.press("ArrowRight");
    expect(await chips.evaluateAll((bs) => bs.filter((b) => b.tabIndex === 0).map((b) => b.textContent.trim()))).toEqual([order[1]]);
    await app.keyboard.press("Tab");                                   // one press leaves the words
    expect(await app.evaluate(() => !!document.activeElement.closest(".ed-tl-words"))).toBe(false);
  });

  test("Tab order: player controls → timeline → inspector (owner 2026-10-14)", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect(app.locator("#edTlInner")).toBeVisible();
    const order = await app.evaluate(() => {
      const after = (a, b) => !!(document.querySelector(a).compareDocumentPosition(document.querySelector(b)) & Node.DOCUMENT_POSITION_FOLLOWING);
      return [after(".ed-pctrl", ".ed-tlwrap"), after(".ed-tlwrap", ".ed-insp"), after(".ed-insp", ".ed-foot")];
    });
    expect(order).toEqual([true, true, true]);
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

  // 2b: a real 4 s clip so the player can play, seek and report duration.
  const CLIP = require("fs").readFileSync(require("path").join(__dirname, "..", "media", "clip-4s.webm"));
  async function openWithVideo(app, api, sound) {
    await mockEditor(app, api);
    api.editor.candidate.has_preview = true;
    await app.route(/\/candidates\/cand-a\/preview(\?.*)?$/, (r) => {    // byte ranges, or the browser can't seek
      const m = /bytes=(\d+)-(\d*)/.exec(r.request().headers()["range"] || "");
      if (!m) return r.fulfill({ status: 200, contentType: "video/webm", headers: { "Accept-Ranges": "bytes" }, body: CLIP });
      const a = +m[1], b = m[2] ? Math.min(+m[2], CLIP.length - 1) : CLIP.length - 1;
      return r.fulfill({ status: 206, contentType: "video/webm", body: CLIP.subarray(a, b + 1),
        headers: { "Accept-Ranges": "bytes", "Content-Range": `bytes ${a}-${b}/${CLIP.length}` } });
    });
    await app.evaluate((v) => { try { v ? localStorage.setItem("clipflow.editor.sound", JSON.stringify(v)) : localStorage.removeItem("clipflow.editor.sound"); } catch {} }, sound || null);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await expect.poll(() => app.locator("#edVideo").evaluate((v) => v.duration || 0)).toBeGreaterThan(3);
  }
  const vid = (app, f) => app.locator("#edVideo").evaluate(f);

  test("Preview sound: speaker toggles + is remembered with the volume; Audio tab says edits are heard after Render preview", async ({ app, api }) => {
    await openWithVideo(app, api, { muted: true, volume: 0.4 });
    const mute = app.locator("[data-ed-mute]");
    await expect(mute).toHaveAttribute("aria-label", "Unmute");
    expect(await vid(app, (v) => [v.muted, v.volume])).toEqual([true, 0.4]);
    await app.locator('[data-ed-tab="audio"]').click();
    await expect(app.locator("#edAudioNote")).toContainText("heard after Render preview");
    await expect(app.locator("#edAudioNote")).toContainText("The player is muted");
    await mute.click();
    await expect(mute).toHaveAttribute("aria-label", "Mute");
    expect(await vid(app, (v) => v.muted)).toBe(false);
    await expect(app.locator("#edAudioNote")).not.toContainText("The player is muted");
    await app.locator('[data-ed-tab="effects"]').click();             // re-render keeps the choice
    expect(await vid(app, (v) => v.muted)).toBe(false);
    expect(await app.evaluate(() => JSON.parse(localStorage.getItem("clipflow.editor.sound")))).toEqual({ muted: false, volume: 0.4 });
  });

  test("Player: sound on by default; Space/K, arrows (Shift = 1 s), J/L, M; keys ignored while typing; scrub bar seeks", async ({ app, api }, info) => {
    await openWithVideo(app, api, null);
    expect(await vid(app, (v) => v.volume)).toBe(1);
    await app.evaluate(() => { const v = document.getElementById("edVideo"); v.pause(); v.currentTime = 1; document.activeElement?.blur(); });
    await expect.poll(() => vid(app, (v) => v.currentTime)).toBe(1);
    await app.keyboard.press("ArrowRight");
    await expect.poll(() => vid(app, (v) => +v.currentTime.toFixed(2))).toBe(1.1);
    await app.keyboard.press("Shift+ArrowRight");
    await expect.poll(() => vid(app, (v) => +v.currentTime.toFixed(2))).toBe(2.1);
    await app.keyboard.press("j");
    await expect.poll(() => vid(app, (v) => +v.currentTime.toFixed(2))).toBe(1.1);
    await app.keyboard.press("Space");
    await expect.poll(() => vid(app, (v) => v.paused)).toBe(false);
    await app.keyboard.press("l");
    await expect.poll(() => vid(app, (v) => v.playbackRate)).toBe(1.5);
    await app.keyboard.press("k");
    await expect.poll(() => vid(app, (v) => [v.paused, v.playbackRate])).toEqual([true, 1]);
    const was = await vid(app, (v) => v.muted);
    await app.keyboard.press("m");
    await expect.poll(() => vid(app, (v) => v.muted)).toBe(!was);
    await app.locator('[data-ed-tab="captions"]').click();
    await app.locator("#edCapText").focus();                         // typing never seeks
    await expect(app.locator("#edCapText")).toBeFocused();
    const t0 = await vid(app, (v) => v.currentTime);
    await app.keyboard.press("ArrowLeft"); await app.keyboard.press("Space");
    expect(await vid(app, (v) => [v.currentTime, v.paused])).toEqual([t0, true]);
    const bar = await app.locator("#edScrub").boundingBox();
    await app.mouse.click(bar.x + bar.width * 0.75, bar.y + bar.height / 2);
    await expect.poll(() => vid(app, (v) => Math.round(v.currentTime / v.duration * 100))).toBeGreaterThanOrEqual(72);
    expect(await app.locator("#edScrubFill").evaluate((e) => e.style.transform)).toMatch(/^scaleX\(0\.7/);
    await app.evaluate(() => { const v = document.getElementById("edVideo"); v.currentTime = v.duration - 0.05; });
    await expect.poll(() => app.locator("#edScrubFill").evaluate((e) => e.style.transform)).toMatch(/^scaleX\(0\.9/);
    expect(await app.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);   // knob at 100 % stays inside
    if (info.project.name === "desktop") {                           // controls row never under the action bar or pill
      const pc = await app.locator(".ed-pctrl").boundingBox(), foot = await app.locator(".ed-foot").boundingBox();
      expect(foot.y >= pc.y + pc.height || foot.x >= pc.x + pc.width).toBe(true);
    }
  });

  test("Timeline: dragging the ruler/waveform scrubs the video; the playhead moves by transform", async ({ app, api }) => {
    await openWithVideo(app, api, { muted: true, volume: 1 });
    await app.evaluate(() => { const v = document.getElementById("edVideo"); v.pause(); v.currentTime = 0; });
    await app.evaluate(() => {                                        // phone: just under the sticky player
      const a = document.querySelector("[data-ed-seekarea]").getBoundingClientRect(), p = document.querySelector(".ed-player").getBoundingClientRect();
      if (a.top < p.bottom || a.bottom > innerHeight - 200) window.scrollBy(0, a.top - p.bottom - 8);
    });
    const area = await app.locator("[data-ed-seekarea]").boundingBox();
    const y = area.y + 30;                                             // waveform band, no chips there
    await app.mouse.move(area.x + 40, y); await app.mouse.down();       // clear of the trim handle at 0
    for (let i = 1; i <= 8; i++) await app.mouse.move(area.x + 40 + i * 25, y);
    await app.mouse.up();
    await expect.poll(() => vid(app, (v) => v.currentTime)).toBeGreaterThan(1);
    expect(await app.locator("#edPlayhead").evaluate((e) => e.style.transform)).toMatch(/^translateX\(/);
  });

  test("Timeline keys (audit Low): focus the timeline, then Space plays/pauses, arrows step (Shift 1 s), Home/End; not in text fields", async ({ app, api }) => {
    await openWithVideo(app, api, { muted: true, volume: 1 });
    await app.evaluate(() => { const v = document.getElementById("edVideo"); v.pause(); v.currentTime = 1; });
    const tl = app.locator("#edTlInner");
    await tl.focus();
    await expect(tl).toBeFocused();
    await app.keyboard.press("ArrowRight");
    await expect.poll(() => vid(app, (v) => +v.currentTime.toFixed(2))).toBe(1.1);
    await app.keyboard.press("Shift+ArrowLeft");
    await expect.poll(() => vid(app, (v) => +v.currentTime.toFixed(2))).toBe(0.1);
    await app.keyboard.press("End");
    await expect.poll(() => vid(app, (v) => v.duration - v.currentTime)).toBeLessThan(0.1);
    await app.keyboard.press("Home");
    await expect.poll(() => vid(app, (v) => v.currentTime)).toBe(0);
    await app.keyboard.press("Space");
    await expect.poll(() => vid(app, (v) => v.paused)).toBe(false);
    await app.keyboard.press("Space");
    await expect.poll(() => vid(app, (v) => v.paused)).toBe(true);
    await app.locator('[data-ed-tab="effects"]').click();
    const range = app.locator("[data-ed-zoom-intensity]");             // a slider keeps its own arrows
    await range.focus();
    const t0 = await vid(app, (v) => v.currentTime);
    await app.keyboard.press("ArrowRight");
    expect(await vid(app, (v) => v.currentTime)).toBe(t0);
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

  test("tabs never clip a label (row scrolls + fades); keyword words show whole rows and scroll inside", async ({ app, api }) => {
    await app.setViewportSize({ width: 360, height: 780 });
    await openEd(app, api);
    const tabs = await app.locator(".ed-seg button").evaluateAll((bs) => bs.map((b) => b.scrollWidth - b.clientWidth));
    expect(Math.max(...tabs)).toBeLessThanOrEqual(0);
    const seg = app.locator(".ed-seg");
    if (await seg.evaluate((e) => e.scrollWidth > e.clientWidth)) {
      await expect(seg).toHaveClass(/more-end/);
      await app.locator('[data-ed-tab="export"]').click();
      await expect(seg).toHaveClass(/more-start/);
      await app.locator('[data-ed-tab="captions"]').click();
    }
    const kw = app.locator(".ed-kw");
    await expect(kw).toHaveCount(1);
    const m = await kw.evaluate((e) => { const b = e.querySelector("button"), gap = parseFloat(getComputedStyle(e).rowGap) || 0;
      return { h: e.clientHeight, row: b.offsetHeight + gap, over: e.scrollHeight - e.clientHeight > 4, ov: getComputedStyle(e).overflowY }; });
    expect(m.ov).toBe("auto");
    if (m.over) {
      await expect(app.locator("#edKwMore")).toBeVisible();
      await kw.evaluate((e) => { e.scrollTop = e.scrollHeight; });
      await expect(app.locator("#edKwMore")).toBeHidden();
    }
  });

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

// Auto Edit E1: Generate plan → list + timeline markers; toggling saves the items (PUT /plan).
test.describe("Editor Auto edit plan", () => {
  test.use({ reducedMotion: "reduce" });
  test("generate, see markers, toggle one off from the timeline", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="effects"]').click();
    await app.locator("[data-ed-plan-gen]").click();
    await expect(app.locator(".ed-plan-row")).toHaveCount(2);
    await expect(app.locator(".ed-plan-row").nth(1)).not.toContainText("arrives in");   // E2: shake renders
    await expect(app.locator(".ed-plan-mark")).toHaveCount(2);
    await expect(app.locator("[data-ed-plan-gen]")).toHaveText("Regenerate plan");
    await app.locator('.ed-plan-mark[data-ed-plan-item="punch-50"]').click();
    await expect(app.locator('.ed-plan-mark[data-ed-plan-item="punch-50"]')).toHaveAttribute("aria-pressed", "false");
    await expect(app.locator('.ed-switch[data-ed-plan-item="punch-50"]')).toHaveAttribute("aria-checked", "false");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/plan")).pop()?.body.items.map((i) => i.on))
      .toEqual([false, true]);
  });
});

// Auto Edit E2: switch an item's effect (motion / time); a freeze adds its hold to the output length.
test.describe("Editor Auto edit E2 effects", () => {
  test.use({ reducedMotion: "reduce" });
  test("change an item to Freeze frame: PUT carries the effect + default params, output grows", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="effects"]').click();
    await app.locator("[data-ed-plan-gen]").click();
    await expect(app.locator(".ed-plan-row")).toHaveCount(2);
    await app.locator('[data-ed-plan-fx="shake-350"]').selectOption("freeze");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/plan")).pop()?.body.items.find((i) => i.id === "shake-350"))
      .toMatchObject({ effect: "freeze", params: { hold: 0.6 } });
    await expect(app.locator('.ed-plan-mark[data-ed-plan-item="shake-350"]')).toHaveClass(/fx-freeze/);
    await expect(app.locator("#edOut")).toContainText("6.6");                 // 6 s clip + 0.6 s hold
  });
});

// Auto Edit E3: a sound per item and an emoji per emoji item (params.sfx / params.emoji).
test.describe("Editor Auto edit E3 sound + emoji", () => {
  test.use({ reducedMotion: "reduce" });
  test("pick a sound, switch to emoji and pick 💀: PUT carries the params", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="effects"]').click();
    await app.locator("[data-ed-plan-gen]").click();
    await app.locator('[data-ed-plan-sfx="punch-50"]').selectOption("boom");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/plan")).pop()?.body.items.find((i) => i.id === "punch-50")?.params)
      .toEqual({ sfx: "boom" });
    await app.locator('[data-ed-plan-fx="shake-350"]').selectOption("emoji");
    await app.locator('[data-ed-plan-emoji="shake-350"]').selectOption("💀");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/plan")).pop()?.body.items.find((i) => i.id === "shake-350")?.params)
      .toEqual({ emoji: "💀" });
  });
});

// Auto Edit E4: Look = colour preset chips + vignette + grain switches (PUT /look).
test.describe("Editor Auto edit E4 look", () => {
  test.use({ reducedMotion: "reduce" });
  test("pick Moody and vignette: PUT /look", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="effects"]').click();
    await app.locator('[data-ed-look-preset="moody"]').click();
    await app.locator("[data-ed-look-vignette]").click();
    await expect(app.locator('[data-ed-look-preset="moody"]')).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => api.calls.filter((c) => c.method === "PUT" && c.path.endsWith("/look")).pop()?.body)
      .toEqual({ preset: "moody", vignette: true, grain: false });
  });
});

// Auto Edit E5: style pack chips (campaign default tagged); applying one is a two-tap action, then the editor reloads.
test.describe("Editor Auto edit E5 style pack", () => {
  test.use({ reducedMotion: "reduce" });
  test("campaign default shown; Gaming Hype applies after a second tap and stays on Effects", async ({ app, api }) => {
    await mockEditor(app, api);
    await app.evaluate(() => { location.hash = "#editor/job-done/cand-a"; });
    await app.locator('[data-ed-tab="effects"]').click();
    await expect(app.locator('[data-ed-pack="podcast_clean"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator(".ed-panel .tag")).toHaveText("from campaign");
    await app.locator('[data-ed-pack="gaming_hype"]').click();
    expect(api.calls.some((c) => c.path && c.path.endsWith("/pack"))).toBe(false);          // first tap only arms
    await app.locator('[data-ed-pack="gaming_hype"]').click();
    await expect.poll(() => api.calls.find((c) => c.method === "POST" && c.path.endsWith("/pack"))?.body).toEqual({ pack: "gaming_hype" });
    await expect(app.locator('[data-ed-pack="gaming_hype"]')).toHaveAttribute("aria-pressed", "true");
    await expect(app.locator('[data-ed-tab="effects"]')).toHaveAttribute("aria-selected", "true");
    await expect(app.locator('[data-ed-look-preset="vivid_gaming"]')).toHaveAttribute("aria-pressed", "true");
  });
});
