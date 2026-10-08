// Publish = stepper step 7. 130 built it as rows per clip × platform; 144 makes it ONE CARD PER CLIP: shared
// actions (Download, Copy title, Send to phone), a platform strip whose chips show each post's status, and a
// panel per chip (Copy caption, Mark posted, views, claim advice, claimed/paid; bottom sheet on mobile).
// Filters: campaign + "Left to post" (default) / All. Same data (clip_posts per platform); amounts pre-formatted.
const { test, expect, openAccount } = require("../fixtures");

const row = (over) => ({ candidate_id: "cand-a", job_id: "job-done", job_title: "Mock stream", title: "Lompatan GILA", caption: "Gila banget\n\n#ime #imeroleplay",
  caption_trimmed: false, hashtags: ["#ime", "#imeroleplay"], platform: "tiktok", platform_name: "TikTok", duration: 34, rendered_at: null,
  has_thumbnail: false, filename: "ime-roleplay_tiktok_lompatan-gila.mp4", post: null, ...over });
const posted = (over) => ({ id: "p-x", status: "posted", account_handle: "imeclips", url: "https://www.tiktok.com/@imeclips/video/1",
  posted_at: new Date().toISOString(), eligible: true, ...over });

function seed(api) {
  api.publishGroups = [
    { campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: [
      row({ campaign: "ime-roleplay" }),
      row({ campaign: "ime-roleplay", platform: "instagram", platform_name: "Instagram Reels", post: posted({ id: "p0", status: "claimed", account_handle: "imeig", views: 41000 }) }),
      row({ campaign: "ime-roleplay", platform: "youtube", platform_name: "YouTube Shorts", post: posted({ id: "p1", account_handle: "imeyt", views: 12000 }) }),
      row({ candidate_id: "cand-done", campaign: "ime-roleplay", title: "All done", post: posted({ id: "p2" }) }),
    ] },
    { campaign: null, campaign_name: "No campaign", rows: [row({ candidate_id: "cand-b", title: "Solo clip", caption: "Just a clip", hashtags: [], platform: "youtube", platform_name: "YouTube Shorts" })] },
  ];
  api.cardExpected = { "cand-a": "Rp 24.000" };
}
async function openPublish(app) {
  await app.locator('#flow [data-nav="publish"]').click();
  await expect(app.locator("#publishSection")).toBeVisible();
  await expect(app.locator("#pageTitle")).toHaveText("Publish");
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Publish");
}
const card = (app, cid) => app.locator(`[data-publish-card="${cid}"]`);

test("one card per clip: chips per platform, summary, filters, card download", async ({ app, api }) => {
  seed(api);
  await openPublish(app);
  await expect(app.locator(".qgroup h3")).toHaveText(["IME Roleplay", "No campaign"]);
  await expect(app.locator("[data-publish-card]")).toHaveCount(2);           // "Left to post": cand-done is hidden
  const a = card(app, "cand-a");
  await expect(a.locator(".pcard-src")).toHaveText("Mock stream");
  await expect(a.locator(".pcard-sum")).toHaveText("Posted on 2 of 3 · Rp 24.000 expected");
  await expect(a.locator("[data-chip]")).toHaveCount(3);
  await expect(a.locator('[data-chip="cand-a:tiktok"]')).toHaveClass(/is-ready/);
  await expect(a.locator('[data-chip="cand-a:tiktok"] .pstat-st')).toHaveText("Ready");
  await expect(a.locator('[data-chip="cand-a:instagram"] .pstat-st')).toHaveText("Claimed");
  await expect(a.locator('[data-chip="cand-a:instagram"] .pstat-views')).toHaveText("41.000 views");
  await expect(a.locator('[data-chip="cand-a:youtube"] .pstat-st')).toHaveText("Posted @imeyt");
  const dl = a.locator("[data-download]");
  await expect(dl).toHaveAttribute("download", "ime-roleplay_lompatan-gila.mp4");
  await expect(dl).toHaveAttribute("href", /\/api\/jobs\/job-done\/candidates\/cand-a\/render\?.*download=clip/);
  await expect(app.locator(".ppanel")).toHaveCount(0);                       // panels exist only while open
  await app.click('[data-publish-filter="all"]');
  await expect(app.locator("[data-publish-card]")).toHaveCount(3);
  await expect(card(app, "cand-done").locator(".pcard-sum")).toHaveText("Posted on 1 of 1");
  await app.click('[data-publish-campaign=""]');
  await expect(app.locator(".qgroup h3")).toHaveText(["No campaign"]);
  await expect(app.locator("[data-publish-card]")).toHaveCount(1);
});

test("copy title (card) and platform caption (panel): Clipboard API and the execCommand fallback", async ({ app, api, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  seed(api);
  await openPublish(app);
  await card(app, "cand-a").locator('[data-chip="cand-a:tiktok"]').click();
  const cap = app.locator('[data-publish-row="cand-a:tiktok"] [data-copy-caption]');
  await cap.click();
  await expect(cap).toHaveText("Copied");
  expect(await app.evaluate(() => navigator.clipboard.readText())).toBe("Gila banget\n\n#ime #imeroleplay");
  await app.keyboard.press("Escape");
  await expect(app.locator(".ppanel")).toHaveCount(0);
  await expect(app.locator('[data-chip="cand-a:tiktok"]')).toBeFocused();
  // Older iOS Safari: no async clipboard → selected textarea + execCommand("copy") within the same tap.
  await app.evaluate(() => { window.__copied = null; Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    const orig = document.execCommand.bind(document); document.execCommand = (c) => { if (c === "copy") { window.__copied = document.activeElement.value; return true; } return orig(c); }; });
  const title = card(app, "cand-a").locator("[data-copy-title]");
  await title.click();
  await expect(title).toHaveText("Copied");
  expect(await app.evaluate(() => window.__copied)).toBe("Lompatan GILA");
});

test("Mark posted from a chip's panel: no account → Settings hint; with one → POST /api/posts, chip Posted @account", async ({ app, api }) => {
  seed(api);
  await openPublish(app);
  await app.click('[data-chip="cand-a:tiktok"]');
  await app.click('[data-publish-row="cand-a:tiktok"] [data-mark-open]');
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .qnote')).toContainText("No active TikTok account");
  api.accounts = [{ id: "acc-tt", platform: "tiktok", platform_name: "TikTok", handle: "imeclips", note: null, active: true }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/accounts"));
  await app.locator('#flow [data-nav="publish"]').click();
  await app.click('[data-chip="cand-a:tiktok"]');
  await app.click('[data-publish-row="cand-a:tiktok"] [data-mark-open]');
  const form = app.locator('[data-mark-form="cand-a:tiktok"]');
  await form.locator("input").fill("tiktok.com/@imeclips/video/1");
  await form.locator("button[type=submit]").click();
  await expect(form.locator(".account-msg")).toContainText("https://");
  await form.locator("input").fill("https://www.tiktok.com/@imeclips/video/1");
  await form.locator("button[type=submit]").click();
  await expect(app.locator('[data-chip="cand-a:tiktok"] .pstat-st')).toHaveText("Posted @imeclips");
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .ppanel-when')).toContainText("@imeclips");
  await expect(app.locator('[data-publish-row="cand-a:tiktok"] .ppanel-when a')).toHaveText("Open post");
  expect(api.calls.find((c) => c.method === "POST" && c.path === "/api/posts").body).toEqual(
    { candidate_id: "cand-a", platform: "tiktok", account_id: "acc-tt", status: "posted", url: "https://www.tiktok.com/@imeclips/video/1" });
});

test("169: the stepper pill keeps every shown step on one row inside the viewport", async ({ app }) => {
  const r = await app.locator("#flow li").evaluateAll((els) => els.filter((e) => e.offsetParent)
    .map((e) => { const b = e.getBoundingClientRect(); return [Math.round(b.top), b.left >= 0 && b.right <= innerWidth]; }));
  expect(r.length).toBe(test.info().project.name === "mobile" ? 6 : 8);   // phone hides the two "Coming in P3" steps
  expect(new Set(r.map((x) => x[0])).size).toBe(1);
  expect(r.every((x) => x[1])).toBe(true);
});

test("pre-post checks: Blocked (red) and Not eligible (amber) chips; panel lists them, red blocks Mark posted", async ({ app, api }) => {
  api.accounts = [{ id: "acc-1", platform: "tiktok", platform_name: "TikTok", handle: "imeclips", active: true },
                  { id: "acc-2", platform: "tiktok", platform_name: "TikTok", handle: "imespare", active: true }];
  api.publishGroups = [{ campaign: "ime-roleplay", campaign_name: "IME Roleplay", rows: [
    row({ campaign: "ime-roleplay", checks: [
      { level: "warn", code: "outside_window", message: "Outside IME Roleplay week window (W1–W4: 1 Oct–28 Oct)" },
      { level: "warn", code: "account_cap", account_id: "acc-1", message: "Cap reached for @imeclips on TikTok this month (2 of 2)" }],
      account_usage: { "acc-1": { used: 2, cap: 2 }, "acc-2": { used: 0, cap: 2 } } }),
    row({ campaign: "ime-roleplay", platform: "facebook", platform_name: "Facebook Reels",
      checks: [{ level: "block", code: "hashtags", message: "Hashtags missing or out of order" }, { level: "warn", code: "length", message: "Over 90 s for Facebook Reels (104 s)" }] }),
  ] }];
  await app.reload(); await app.waitForResponse((r) => r.url().includes("/api/accounts"));
  await openPublish(app);
  await expect(app.locator('[data-chip="cand-a:facebook"]')).toHaveClass(/is-block/);
  await expect(app.locator('[data-chip="cand-a:facebook"] .pstat-st')).toHaveText("Blocked");
  await expect(app.locator('[data-chip="cand-a:tiktok"]')).toHaveClass(/is-warn/);
  await expect(app.locator('[data-chip="cand-a:tiktok"] .pstat-st')).toHaveText("Not eligible");
  await app.click('[data-chip="cand-a:facebook"]');
  const red = app.locator('[data-publish-row="cand-a:facebook"]');
  await expect(red.locator(".qcheck.is-block")).toHaveText("Hashtags missing or out of order");
  await expect(red.locator(".qcheck.is-warn")).toHaveText("Over 90 s for Facebook Reels (104 s)");
  await expect(red.locator("[data-mark-open]")).toBeDisabled();
  if (test.info().project.name === "mobile") await app.keyboard.press("Escape"); // the bottom sheet covers the strip
  await app.click('[data-chip="cand-a:tiktok"]');                              // one panel per card at a time
  await expect(app.locator(".ppanel")).toHaveCount(1);
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
  await expect(app.locator('[data-chip="cand-a:tiktok"]')).toHaveClass(/is-warn/);   // posted, not eligible → amber
});

test("panel: claim advice, views as of, Mark claimed with views, Mark paid with the difference", async ({ app, api }) => {
  api.publishGroups = [{ campaign: "fandra-octo", campaign_name: "Fandra", rows: [row({ campaign: "fandra-octo", post: posted({
    id: "p-f", account_handle: "fan", url: "https://tiktok.com/@fan/video/1", views: 40000, views_at: new Date().toISOString(),
    advice: { action: "wait", reason: "still_growing", message: "+9.000 views in 24 h; Rp 156.000 now, about Rp 192.000 tomorrow at this pace.", payout_now_fmt: "Rp 156.000", views_needed: 2000, deadline: null } }) })] }];
  await openPublish(app);
  await app.click('[data-publish-filter="all"]');
  await app.click('[data-chip="cand-a:tiktok"]');
  const r = app.locator('[data-publish-row="cand-a:tiktok"]');
  await expect(r.locator(".qadvice .badge")).toHaveText("Wait");
  await expect(r.locator(".qadvice-msg")).toContainText("about Rp 192.000 tomorrow");
  await expect(r.locator(".qviews")).toContainText("Views 40.000 as of");
  await r.locator("[data-views-form] input").fill("45500");
  await r.locator("[data-views-form] button").click();
  await expect(r.locator(".qviews b")).toHaveText("45.500");
  await expect(app.locator('[data-chip="cand-a:tiktok"] .pstat-views')).toHaveText("45.500 views");
  expect(api.calls.find((c) => c.method === "PATCH").body).toEqual({ views: 45500 });
  await r.locator("[data-claim-open]").click();
  await expect(r.locator("[data-claim-form] input")).toHaveValue("45500");
  await r.locator("[data-claim-form] button[type=submit]").click();
  await expect(app.locator('[data-chip="cand-a:tiktok"] .pstat-st')).toHaveText("Claimed");
  await expect(r.locator(".qmoney")).toHaveText("Claimed at 45.500 views · expected Rp 180.000");
  expect(api.calls.filter((c) => c.method === "PATCH").at(-1).body).toEqual({ status: "claimed", views: 45500 });
  await r.locator("[data-claim-open]").click();
  await expect(r.locator("[data-paid-form] input")).toHaveValue("180000");
  await r.locator("[data-paid-form] input").fill("168000");
  await r.locator("[data-paid-form] button[type=submit]").click();
  await expect(r.locator(".qmoney")).toContainText("Paid Rp 168.000 · expected Rp 180.000 · −Rp 12.000");
  await expect(app.locator('[data-chip="cand-a:tiktok"] .pstat-st')).toHaveText("Paid");
  expect(api.calls.filter((c) => c.method === "PATCH").at(-1).body).toEqual({ status: "paid", paid_rp: 168000 });
});

test("Telegram: chat id in Account, test send, Send to phone from the card (video once + every caption)", async ({ app, api }) => {
  await openAccount(app);
  await expect(app.locator("#telegramHint")).toContainText("@clipflow_bot");
  await expect(app.locator("#telegramTest")).toBeDisabled();
  await app.fill("#telegramChat", "not a chat");
  await app.click("#telegramSave");
  await expect(app.locator("#telegramMsg")).toContainText("Chat id");
  await app.fill("#telegramChat", "123456789");
  await app.click("#telegramSave");
  await expect(app.locator("#telegramMsg")).toHaveText("Saved.");
  await expect(app.locator("#telegramTest")).toBeEnabled();
  await app.click("#telegramTest");
  await expect(app.locator("#telegramMsg")).toContainText("Test queued");
  await app.keyboard.press("Escape");
  seed(api);
  await openPublish(app);
  const c = card(app, "cand-a");
  await c.locator("[data-send-phone]").click();
  await expect(c.locator(".qsend")).toHaveText("Sending to your phone…");
  await expect(c.locator("[data-send-phone]")).toBeDisabled();
  expect(api.calls.find((x) => x.path === "/api/publish/send-to-phone").body).toEqual({ candidate_id: "cand-a" });
});

test("layout: chips wrap on one card, panel inline on desktop / bottom sheet on mobile (screenshots)", async ({ app, api }) => {
  seed(api);
  api.publishGroups[0].rows.push(row({ campaign: "ime-roleplay", platform: "facebook", platform_name: "Facebook Reels",
    checks: [{ level: "warn", code: "outside_window", message: "Outside IME Roleplay week window" }] }));
  await openPublish(app);
  const mobile = test.info().project.name === "mobile";
  await expect(app.locator("#publishSection")).not.toHaveClass(/switching-in/);   // view switch done (its transform would hold fixed layers)
  await app.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.effect?.getTiming().iterations !== Infinity).map((a) => a.finished)));
  const wide = await app.evaluate(() => [...document.querySelectorAll("#publishSection *")]
    .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).map((e) => e.tagName + "." + e.className));
  expect(wide).toEqual([]);
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await app.screenshot({ path: `test-results/publish-cards-${mobile ? 390 : 1280}.png`, fullPage: true });
  await app.click('[data-chip="cand-a:youtube"]');
  const panel = app.locator(".ppanel");
  await expect(panel).toBeVisible();
  const vh = app.viewportSize().height;
  if (mobile) {
    await expect.poll(async () => { const b = await panel.boundingBox(); return Math.round(b.y + b.height); }).toBe(vh); // docked once it slid up
    await expect(app.locator(".ppanel-scrim")).toBeVisible();
  } else {
    await expect(app.locator(".ppanel-scrim")).toBeHidden();
  }
  await app.screenshot({ path: `test-results/publish-panel-${mobile ? 390 : 1280}.png` });
  if (mobile) await app.locator(".ppanel-scrim").click({ position: { x: 10, y: 10 } });
  else await panel.locator(".ppanel-close").click();
  await expect(app.locator(".ppanel")).toHaveCount(0);
});

test("162: earn label on a card; an ended campaign's clips sit in a collapsed Expired group", async ({ app, api }) => {
  seed(api);
  api.publishGroups.push({ campaign: "old", campaign_name: "Old campaign", expired: true,
    rows: [row({ candidate_id: "cand-old", title: "Old clip", campaign: "old" })] });
  api.cardEarn = { "cand-a": { code: "week_closed", label: "Week closed" } };
  await openPublish(app);
  await expect(card(app, "cand-a").locator(".pcard-earn")).toHaveText("Week closed");
  const ex = app.locator("[data-publish-expired]");
  await expect(ex.locator("summary")).toHaveText("Expired · 1 clip (campaign ended)");
  await expect(ex).not.toHaveAttribute("open", "");
  await expect(card(app, "cand-old")).toBeHidden();
  await ex.locator("summary").click();
  await expect(card(app, "cand-old")).toBeVisible();
  await expect(app.locator(".qgroup:not(.pexpired) h3")).not.toContainText(["Old campaign"]);
});
