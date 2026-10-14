// 217: Settings → Sound effects. Categories with the sound in use (mine or built-in) + Find sounds (Freesound, CC0,
// nothing assigned unless "Use for …" is clicked), My sounds (play, rename, category, delete + Undo), upload.
const { test, expect, nav } = require("../fixtures");
const SHOTS = process.env.SFX_SHOTS;
const SIZES = { desktop: [1440, 900], mobile: [390, 844] };

const CATS = [["laugh", "Laugh", "laugh", ["Funny / Meme"]], ["ding", "Ding", "ding", ["Funny / Meme"]], ["whoosh", "Whoosh", "whoosh", ["Gaming Hype"]],
  ["boom", "Boom", "boom impact", ["Gaming Hype", "Drama / Tension"]], ["bass_hit", "Bass hit", "bass hit", ["Gaming Hype"]],
  ["record_scratch", "Record scratch", "record scratch", ["Funny / Meme"]]];
const RESULTS = [
  { id: 101, name: "Crowd laugh short", author: "studio-a", duration: 2.1, license: "CC0", url: "https://freesound.org/s/101/", rating: 4.6, ratings: 212, downloads: 15400 },
  { id: 102, name: "Giggle", author: "bob", duration: 1.2, license: "CC0", url: "https://freesound.org/s/102/", rating: 4.1, ratings: 40, downloads: 2100 },
  { id: 103, name: "Sitcom laugh track", author: "c<script>", duration: 3.8, license: "CC0", url: "https://freesound.org/s/103/", rating: 3.9, ratings: 18, downloads: 900 },
];

function sfxState(freesound = true) {
  return { freesound, sounds: [
    { id: "11111111-1111-4111-8111-111111111111", name: "My boom", duration: 1.4, category: "boom", source: "upload", source_url: null, author: null, license: null },
    { id: "22222222-2222-4222-8222-222222222222", name: "Old laugh", duration: 2.0, category: null, source: "freesound", source_url: "https://freesound.org/s/9/", author: "fs-user", license: "http://creativecommons.org/publicdomain/zero/1.0/" },
  ], calls: [] };
}

async function mockSfx(app, st) {
  const view = () => ({
    freesound: st.freesound, limits: { max_bytes: 2097152, max_seconds: 10, min_seconds: 0.3, max_sounds: 50 },
    sounds: st.sounds.map((s) => ({ ...s, category_label: (CATS.find((c) => c[0] === s.category) || [])[1] || null })),
    categories: CATS.map(([key, label, query, used_by]) => {
      const mine = st.sounds.find((s) => s.category === key);
      return { key, label, query, used_by, assigned: mine ? { id: mine.id, name: mine.name } : null, default: mine ? null : key === "laugh" ? "Built-in ding" : "Built-in" };
    }),
  });
  await app.route(/\/sfx\/[a-z_]+\.wav$/, (r) => r.fulfill({ status: 200, contentType: "audio/wav", body: Buffer.alloc(64) }));
  await app.route(/\/api\/sfx(\/|\?|$)/, async (route) => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname, method = req.method();
    const json = (b, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    st.calls.push(`${method} ${path}${url.search}`);
    if (method === "GET" && path === "/api/sfx") return json(view());
    if (method === "GET" && path === "/api/sfx/freesound/search") return json({ query: url.searchParams.get("q"), results: url.searchParams.get("q") === "nothing" ? [] : RESULTS });
    if (method === "GET") return route.fulfill({ status: 200, contentType: "audio/mpeg", body: Buffer.alloc(64) });
    const fs = path.match(/^\/api\/sfx\/freesound\/(\d+)$/);
    if (method === "POST" && fs) {
      const body = req.postDataJSON() || {}, r = RESULTS.find((x) => x.id === +fs[1]);
      if (body.category) st.sounds.forEach((s) => { if (s.category === body.category) s.category = null; });
      st.sounds.unshift({ id: `33333333-3333-4333-8333-33333333333${st.sounds.length}`, name: r.name, duration: r.duration, category: body.category || null, source: "freesound", source_url: r.url, author: r.author, license: "cc0" });
      return json(st.sounds[0]);
    }
    if (method === "POST" && path === "/api/sfx") {
      st.sounds.unshift({ id: "44444444-4444-4444-8444-444444444444", name: "uploaded", duration: 1.0, category: null, source: "upload" });
      return json(st.sounds[0]);
    }
    const one = path.match(/^\/api\/sfx\/([^/]+)$/);
    if (one && method === "PATCH") {
      const body = req.postDataJSON(), s = st.sounds.find((x) => x.id === one[1]);
      if ("category" in body && body.category) st.sounds.forEach((x) => { if (x.category === body.category) x.category = null; });
      Object.assign(s, body);
      return json(s);
    }
    if (one && method === "DELETE") { st.sounds = st.sounds.filter((x) => x.id !== one[1]); return json({ status: "ok" }); }
    return json({ detail: "mock: no sfx fixture" }, 404);
  });
  await app.addInitScript(() => {});
  await app.evaluate(() => { HTMLMediaElement.prototype.play = function () { return Promise.resolve(); }; });
}

async function openSfx(app, st) {
  const [w, h] = SIZES[test.info().project.name];
  await app.setViewportSize({ width: w, height: h });
  await mockSfx(app, st);
  await nav(app, "settings");
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
  await expect(app.locator("#sfxEntrySummary")).toHaveText("2 sounds · 1 in use");
  await app.click("[data-open-sfx]");
  await expect(app.locator("#sfxSheet")).toHaveClass(/open/);
  await expect(app.locator("#settingsSheet")).not.toHaveClass(/open/);
  await expect(app.locator("[data-sfx-cat-row]")).toHaveCount(6);
}
const shot = async (app, name) => { if (SHOTS) await app.screenshot({ path: `${SHOTS}/${name}-${test.info().project.name}.png` }); };

test("categories show the sound in use and who uses it; My sounds lists mine", async ({ app }) => {
  const st = sfxState();
  await openSfx(app, st);
  const laugh = app.locator('[data-sfx-cat-row="laugh"]');
  await expect(laugh.locator(".row-label small")).toHaveText("Built-in ding · Used by Funny / Meme");
  await expect(laugh.locator(".sfx-play")).toHaveAttribute("data-sfx-play", "/sfx/ding.wav");
  const boom = app.locator('[data-sfx-cat-row="boom"]');
  await expect(boom.locator(".row-label small")).toHaveText("Yours: My boom · Used by Gaming Hype, Drama / Tension");
  await expect(boom.locator(".sfx-play")).toHaveAttribute("data-sfx-play", /\/api\/sfx\/11111111-1111-4111-8111-111111111111\/file\?mt=mock-token$/);
  const rows = app.locator("[data-sfx-row]");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1).locator("small")).toHaveText("2.0 s · Freesound · by fs-user · CC0");
  await expect(rows.nth(0).locator("select")).toHaveValue("boom");
  await shot(app, "sfx-sheet");
});

test("Find sounds: CC0 results with preview, Save keeps it unassigned, Use for assigns it", async ({ app }) => {
  const st = sfxState();
  await openSfx(app, st);
  const find = app.locator('[data-sfx-find="laugh"]');
  await expect(find).toHaveAttribute("aria-expanded", "false");
  await find.click();
  await expect(find).toHaveAttribute("aria-expanded", "true");
  const res = app.locator("#sfxRes-laugh .sfx-res");
  await expect(res).toHaveCount(3);
  expect(st.calls).toContain("GET /api/sfx/freesound/search?category=laugh&q=laugh");
  await expect(res.first().locator("small")).toHaveText("2.1 s · CC0 · by studio-a · ★ 4.6 (212) · 15,400 downloads");
  await expect(res.nth(2).locator("small")).toContainText("by c<script>");          // escaped, not markup
  await expect(res.first().locator("a.sfx-src")).toHaveAttribute("href", "https://freesound.org/s/101/");
  await expect(res.first().locator(".sfx-play")).toHaveAttribute("data-sfx-play", /\/api\/sfx\/freesound\/101\/preview\?mt=/);
  await res.first().locator(".sfx-play").click();
  await expect(res.first().locator(".sfx-play")).toHaveAttribute("aria-label", "Stop Crowd laugh short");
  await shot(app, "sfx-find");
  // nothing was assigned by searching or playing
  expect(st.calls.filter((c) => !c.startsWith("GET"))).toEqual([]);
  await res.nth(1).locator('[data-sfx-save="102"]:not([data-sfx-use])').click();
  await expect(app.locator("[data-sfx-row]")).toHaveCount(3);
  expect(st.sounds[0]).toMatchObject({ name: "Giggle", category: null });
  await expect(app.locator('[data-sfx-cat-row="laugh"] > .inset-row .row-label small')).toHaveText(/^Built-in ding/);
  await app.locator('#sfxRes-laugh [data-sfx-save="101"][data-sfx-use]').click();
  await expect(app.locator('[data-sfx-cat-row="laugh"] > .inset-row .row-label small')).toHaveText("Yours: Crowd laugh short · Used by Funny / Meme");
  expect(st.calls).toContain("POST /api/sfx/freesound/101");
});

test("search with no results and a new query", async ({ app }) => {
  await openSfx(app, sfxState());
  await app.click('[data-sfx-find="whoosh"]');
  const input = app.locator("#sfxFind-whoosh input");
  await expect(input).toBeFocused();
  await input.fill("nothing");
  await input.press("Enter");
  await expect(app.locator("#sfxRes-whoosh")).toHaveText(/No CC0 sounds of 0.5–4 s for “nothing”/);
});

test("rename (Esc cancels without closing the sheet), category, delete with Undo", async ({ app }) => {
  const st = sfxState();
  await openSfx(app, st);
  const id = "22222222-2222-4222-8222-222222222222";
  await app.click(`[data-sfx-rename="${id}"]`);
  const inp = app.locator(".sfx-rename-input");
  await inp.fill("Nope");
  await inp.press("Escape");
  await expect(app.locator("#sfxSheet")).toHaveClass(/open/);
  await expect(app.locator(`[data-sfx-row="${id}"] .sfx-name`)).toHaveText("Old laugh");
  await app.click(`[data-sfx-rename="${id}"]`);
  await app.locator(".sfx-rename-input").fill("Big laugh");
  await app.locator(".sfx-rename-input").press("Enter");
  await expect(app.locator(`[data-sfx-row="${id}"] .sfx-name`)).toHaveText("Big laugh");
  await app.selectOption(`[data-sfx-assign="${id}"]`, "laugh");
  await expect(app.locator('[data-sfx-cat-row="laugh"] > .inset-row .row-label small')).toHaveText(/^Yours: Big laugh/);
  await app.click(`[data-sfx-delete="${id}"]`);
  await expect(app.locator("[data-sfx-row]")).toHaveCount(1);
  await app.click("#toastAction");                                                    // Undo
  await expect(app.locator("[data-sfx-row]")).toHaveCount(2);
  expect(st.calls.some((c) => c.startsWith("DELETE"))).toBe(false);
});

test("upload goes through authFetch as multipart", async ({ app }) => {
  const st = sfxState();
  await openSfx(app, st);
  await app.setInputFiles("#sfxUploadInput", { name: "laugh.mp3", mimeType: "audio/mpeg", buffer: Buffer.from("ID3fake") });
  await expect(app.locator("[data-sfx-row]")).toHaveCount(3);
  expect(st.calls).toContain("POST /api/sfx");
});

test("without a Freesound key: Find sounds is disabled, uploads still work", async ({ app }) => {
  await openSfx(app, sfxState(false));
  await expect(app.locator('[data-sfx-find="laugh"]')).toBeDisabled();
  await expect(app.locator("#sfxCats")).toContainText("Freesound search isn't set up yet");
  await expect(app.locator("#sfxDrop")).toBeVisible();
});
