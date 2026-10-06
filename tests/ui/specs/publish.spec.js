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

test("pre-post checks: red blocks Mark posted; warnings show and preview 'not eligible' per account", async ({ app, api }) => {
  api.accounts = [{ id: "acc-1", platform: "tiktok", platform_name: "TikTok", handle: "imeclips", active: true },
                  { id: "acc-2", platform: "tiktok", platform_name: "TikTok", handle: "imespare", active: true }];
  api.publishGroups = [{ campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: [
    row({ campaign: "ime-roleplay", checks: [
      { level: "warn", code: "outside_window", message: "Outside IME Roleplay week window (W1–W4: 1 Oct–28 Oct)" },
      { level: "warn", code: "account_cap", account_id: "acc-1", message: "Cap reached for @imeclips on TikTok this month (2 of 2)" }],
      account_usage: { "acc-1": { used: 2, cap: 2 }, "acc-2": { used: 0, cap: 2 } } }),
    row({ candidate_id: "cand-red", campaign: "ime-roleplay", platform: "facebook", platform_name: "Facebook Reels",
      checks: [{ level: "block", code: "hashtags", message: "Hashtags missing or out of order" }, { level: "warn", code: "length", message: "Over 90 s for Facebook Reels (104 s)" }] }),
  ] }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/accounts"));
  await app.locator('#flow [data-nav="publish"]').click();
  const red = app.locator('[data-publish-row="cand-red:facebook"]');
  await expect(red.locator(".qcheck.is-block")).toHaveText("Hashtags missing or out of order");
  await expect(red.locator(".qcheck.is-warn")).toHaveText("Over 90 s for Facebook Reels (104 s)");
  await expect(red.locator("[data-mark-open]")).toBeDisabled();
  const tt = app.locator('[data-publish-row="cand-a:tiktok"]');
  await expect(tt.locator(".qcheck.is-warn")).toHaveText(["Outside IME Roleplay week window (W1–W4: 1 Oct–28 Oct)", "Cap reached for @imeclips on TikTok this month (2 of 2)"]);
  await tt.locator("[data-mark-open]").click();
  const sel = tt.locator("select");
  await expect(sel.locator("option").first()).toHaveText("@imeclips · 2/2 this month (cap reached)");
  await expect(tt.locator("[data-mark-warn]")).toHaveText(/Will be recorded as not eligible: Outside .*; Cap reached for @imeclips/);
  await sel.selectOption("acc-2");
  await expect(tt.locator("[data-mark-warn]")).toHaveText("Will be recorded as not eligible: Outside IME Roleplay week window (W1–W4: 1 Oct–28 Oct)");
  await tt.locator("input").fill("https://www.tiktok.com/@imespare/video/9");
  await tt.locator("button[type=submit]").click();   // still allowed: warnings never block
  await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path === "/api/posts" && c.body.account_id === "acc-2")).toBe(true);
});

test("claim advice, views as of, Mark claimed with views, Mark paid with the difference", async ({ app, api }) => {
  api.publishGroups = [{ campaign: "fandra-octo", campaign_name: "Fandra", rows: [row({ campaign: "fandra-octo", post: {
    id: "p-f", status: "posted", account_handle: "fan", url: "https://tiktok.com/@fan/video/1", posted_at: new Date().toISOString(),
    views: 40000, views_at: new Date().toISOString(), eligible: true,
    advice: { action: "wait", reason: "still_growing", message: "+9.000 views in 24 h; Rp 156.000 now, about Rp 192.000 tomorrow at this pace.", payout_now_fmt: "Rp 156.000", views_needed: 2000, deadline: null } } })] }];
  await app.locator('#flow [data-nav="publish"]').click();
  const r = app.locator('[data-publish-row="cand-a:tiktok"]');
  await expect(r.locator(".qadvice .badge")).toHaveText("Wait");
  await expect(r.locator(".qadvice-msg")).toContainText("about Rp 192.000 tomorrow");
  await expect(r.locator(".qviews")).toContainText("Views 40.000 as of");
  await r.locator("[data-views-form] input").fill("45500");
  await r.locator("[data-views-form] button").click();
  await expect(r.locator(".qviews b")).toHaveText("45.500");
  expect(api.calls.find((c) => c.method === "PATCH").body).toEqual({ views: 45500 });
  await r.locator("[data-claim-open]").click();
  await expect(r.locator("[data-claim-form] input")).toHaveValue("45500");
  await r.locator("[data-claim-form] button[type=submit]").click();
  await expect(r.locator(".qs .badge").first()).toHaveText("Claimed");
  await expect(r.locator(".qmoney")).toHaveText("Claimed at 45.500 views · expected Rp 180.000");
  expect(api.calls.filter((c) => c.method === "PATCH").at(-1).body).toEqual({ status: "claimed", views: 45500 });
  await r.locator("[data-claim-open]").click();
  await expect(r.locator("[data-paid-form] input")).toHaveValue("180000");
  await r.locator("[data-paid-form] input").fill("168000");
  await r.locator("[data-paid-form] button[type=submit]").click();
  await expect(r.locator(".qmoney")).toContainText("Paid Rp 168.000 · expected Rp 180.000 · −Rp 12.000");
  expect(api.calls.filter((c) => c.method === "PATCH").at(-1).body).toEqual({ status: "paid", paid_rp: 168000 });
});
