// 126: Analyze step = flow-preview step 3. Same POST /api/jobs payload as before the rebuild (keys + values),
// layout cards ↔ jobs.layout, disabled "Coming soon" layouts, estimate shown only with history.
const { test, expect } = require("../fixtures");
const URL = "https://youtu.be/dQw4w9WgXcQ";
const post = (api) => api.calls.filter((c) => c.method === "POST" && c.path === "/api/jobs").at(-1)?.body;

test("default payload is exactly the pre-rebuild one", async ({ app, api }) => {
  await app.fill("#youtubeUrl", URL);
  await app.click("#analyzeButton");
  await expect.poll(() => post(api)).toEqual({
    youtube_url: URL, custom_title: null, layout: "auto", platform: "youtube_shorts", split_ratio: 70,
    subtitle_animation: "karaoke", language: "auto", language_fallback: null, campaign: null, clip_count: 4,
  });
});

test("every control maps onto the same fields", async ({ app, api }) => {
  await app.fill("#youtubeUrl", URL);
  await app.fill("#jobCustomTitle", "My job");
  await app.click('[data-split="60"]');
  await app.click('[data-layout="left"]');
  await app.click('[data-language="id"]');
  await app.click('[data-platform="tiktok"]');
  await app.locator("#jobCampaign").selectOption("windah");
  await app.click('[data-clips="6"]');
  await app.click("#analyzeButton");
  await expect.poll(() => post(api)).toEqual({
    youtube_url: URL, custom_title: "My job", layout: "left", platform: "tiktok", split_ratio: 60,
    subtitle_animation: "karaoke", language: "id", language_fallback: "id", campaign: "windah", clip_count: 6,
  });
});

test("Full frame sends layout none and hides the facecam options; facecam card restores the cam position", async ({ app, api }) => {
  await app.click('[data-layout="right"]');
  await app.click('[data-layout-card="full"]');
  await expect(app.locator("#facecamOpts")).toBeHidden();
  await app.fill("#youtubeUrl", URL);
  await app.click("#analyzeButton");
  await expect.poll(() => post(api)?.layout).toBe("none");
  await app.click('[data-layout-card="facecam"]');
  await expect(app.locator("#facecamOpts")).toBeVisible();
  await expect(app.locator('[data-layout="right"]')).toHaveAttribute("aria-pressed", "true");
});

test("unbuilt layouts are disabled Coming soon cards", async ({ app }) => {
  const off = app.locator(".layout-opt:disabled");
  await expect(off).toHaveCount(3);
  for (const n of ["Speaker follow", "Two-speaker stacked", "Wide + blur"]) await expect(off.filter({ hasText: n })).toContainText("Coming soon");
});

test("estimate hidden without history, shown with it", async ({ app, api }) => {
  await expect(app.locator("#analyzeEstimate")).toBeHidden();
  api.estimate = { samples: 5, video_seconds: 5040, processing_seconds: 372, seconds_per_video_minute: 4.4 };
  await app.reload();
  await expect(app.locator("#analyzeEstimate")).toHaveText("≈ 6 min for a 1 h 24 min video");
});

test("subtitle defaults line links to Settings", async ({ app, api }) => {
  api.settings = { DEFAULT_SUBTITLE_STYLE: { value: "bold", source: "default", scope: "user" },
    DEFAULT_SUBTITLE_FONT: { value: "Montserrat Black", source: "user", scope: "user" },
    DEFAULT_SUBTITLE_SIZE: { value: "72", source: "default", scope: "user" } };
  await app.reload();
  await expect(app.locator("#subtitleDefaultsText")).toContainText("Montserrat Black · 72 px · karaoke");
  await app.locator('#subtitleDefaults [data-nav="settings"]').click();
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
  await expect(app.locator("#set-DEFAULT_SUBTITLE_FONT")).toHaveValue("Montserrat Black");
});

test("clips: default from your setting, campaign default tagged, explicit pick wins (136)", async ({ app, api }) => {
  api.settings = { CLIPS_PER_JOB: { value: "2", source: "user", scope: "user" } };
  api.campaigns = [...api.campaigns, { slug: "six", name: "Six clips", brief_pending: false, platforms: [], default_layout: "auto", default_clip_count: 6, sources: [], hashtags: [] }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/campaigns"));
  await expect(app.locator('[data-clips="2"]')).toHaveAttribute("aria-pressed", "true");
  await app.locator("#jobCampaign").selectOption("six");
  await expect(app.locator('[data-clips="6"]')).toHaveAttribute("aria-pressed", "true");
  await expect(app.locator("#clipsFromCampaign")).toBeVisible();
  await app.click('[data-clips="4"]');
  await app.locator("#jobCampaign").selectOption("");
  await expect(app.locator('[data-clips="4"]')).toHaveAttribute("aria-pressed", "true");
  await app.fill("#youtubeUrl", URL); await app.click("#analyzeButton");
  await expect.poll(() => post(api)?.clip_count).toBe(4);
});
