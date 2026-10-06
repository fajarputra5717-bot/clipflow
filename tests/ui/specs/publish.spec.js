// P2 part 3 (130): Publish = stepper step 7 (flow-preview "Publish queue"): rows per clip × platform grouped by
// campaign, platform filter, Download (campaign_platform_slug.mp4), Copy title / caption (Clipboard API and the
// execCommand fallback older iOS Safari needs), Mark posted (account + link → POST /api/posts), status badges.
const { test, expect } = require("../fixtures");

const row = (over) => ({ candidate_id: "cand-a", job_id: "job-done", job_title: "Mock stream", title: "Lompatan GILA", caption: "Gila banget\n\n#ime #imeroleplay",
  caption_trimmed: false, hashtags: ["#ime", "#imeroleplay"], platform: "tiktok", platform_name: "TikTok", duration: 34, rendered_at: null,
  has_thumbnail: false, filename: "ime-roleplay_tiktok_lompatan-gila.mp4", post: null, ...over });

async function openPublish(app, api) {
  api.publishGroups = [
    { campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: [row(), row({ platform: "instagram", platform_name: "Instagram Reels", filename: "ime-roleplay_instagram_lompatan-gila.mp4",
      post: { id: "p0", status: "claimed", account_handle: "imeig", url: "https://instagram.com/reel/x", posted_at: new Date().toISOString() } })] },
    { campaign: null, campaign_name: "No campaign", rows: [row({ candidate_id: "cand-b", title: "Solo clip", caption: "Just a clip", hashtags: [], platform: "youtube", platform_name: "YouTube Shorts", filename: "clip_youtube_solo-clip.mp4" })] },
  ];
  await app.locator('#flow [data-nav="publish"]').click();
  await expect(app.locator("#publishSection")).toBeVisible();
  await expect(app.locator("#pageTitle")).toHaveText("Publish");
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Publish");
}

test("queue rows, grouping, filter, statuses and download names", async ({ app, api }) => {
  await openPublish(app, api);
  await expect(app.locator(".qgroup h3")).toHaveText(["IME Roleplay", "No campaign"]);
  await expect(app.locator("[data-publish-row]")).toHaveCount(3);
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .badge')).toHaveText("Ready");
  await expect(app.locator('[data-publish-row="cand-a:instagram"] .badge')).toHaveText("Claimed");
  await expect(app.locator('[data-publish-row="cand-a:instagram"] [data-mark-open]')).toHaveCount(0);
  const dl = app.locator('[data-publish-row="cand-a:tiktok"] [data-download]');
  await expect(dl).toHaveAttribute("download", "ime-roleplay_tiktok_lompatan-gila.mp4");
  await expect(dl).toHaveAttribute("href", /\/api\/jobs\/job-done\/candidates\/cand-a\/render\?.*download=tiktok/);
  await app.click('[data-publish-filter="youtube"]');
  await expect(app.locator("[data-publish-row]")).toHaveCount(1);
  await expect(app.locator(".qgroup h3")).toHaveText(["No campaign"]);
});

test("copy title and caption: Clipboard API and the execCommand fallback", async ({ app, api, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await openPublish(app, api);
  const cap = app.locator('[data-publish-row="cand-a:tiktok"] [data-copy-caption]');
  await cap.click();
  await expect(cap).toHaveText("Copied");
  expect(await app.evaluate(() => navigator.clipboard.readText())).toBe("Gila banget\n\n#ime #imeroleplay");
  // Older iOS Safari: no async clipboard → selected textarea + execCommand("copy") within the same tap.
  await app.evaluate(() => { window.__copied = null; Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    const orig = document.execCommand.bind(document); document.execCommand = (c) => { if (c === "copy") { window.__copied = document.activeElement.value; return true; } return orig(c); }; });
  const title = app.locator('[data-publish-row="cand-a:tiktok"] [data-copy-title]');
  await title.click();
  await expect(title).toHaveText("Copied");
  expect(await app.evaluate(() => window.__copied)).toBe("Lompatan GILA");
});

test("Mark posted: no account → Settings hint; with one → POST /api/posts and status Posted", async ({ app, api }) => {
  await openPublish(app, api);
  await app.click('[data-publish-row="cand-a:tiktok"] [data-mark-open]');
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .qnote')).toContainText("No active TikTok account");
  api.accounts = [{ id: "acc-tt", platform: "tiktok", platform_name: "TikTok", handle: "imeclips", note: null, active: true }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/accounts"));
  await app.locator('#flow [data-nav="publish"]').click();
  await app.click('[data-publish-row="cand-a:tiktok"] [data-mark-open]');
  const form = app.locator('[data-mark-form="cand-a:tiktok"]');
  await form.locator("input").fill("tiktok.com/@imeclips/video/1");
  await form.locator("button[type=submit]").click();
  await expect(form.locator(".account-msg")).toContainText("https://");
  await form.locator("input").fill("https://www.tiktok.com/@imeclips/video/1");
  await form.locator("button[type=submit]").click();
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .badge')).toHaveText("Posted");
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .qwhen')).toContainText("@imeclips");
  expect(api.calls.find((c) => c.method === "POST" && c.path === "/api/posts").body).toEqual(
    { candidate_id: "cand-a", platform: "tiktok", account_id: "acc-tt", status: "posted", url: "https://www.tiktok.com/@imeclips/video/1" });
});

test("mobile tab bar keeps every item on one row (Publish added)", async ({ app }) => {
  test.skip(test.info().project.name !== "mobile");
  const ys = await app.locator("#tabbar .tabbar-item").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
  expect(ys.length).toBe(5);
  expect(new Set(ys).size).toBe(1);
});
