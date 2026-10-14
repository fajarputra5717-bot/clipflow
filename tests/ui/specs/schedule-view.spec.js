// P2.5 S3 (147): stepper step 6 "Schedule" = own planned posts by WIB day (list; week calendar ≥ 1000 px), overdue
// on top in red, render state + eligibility chips, free suggested times on empty days, row actions.
const { test, expect, menuItem } = require("../fixtures");
test.use({ reducedMotion: "reduce" });

const wibKey = (d) => new Date(d.getTime() + 7 * 3600e3).toISOString().slice(0, 10);
const hoursFromNow = (h) => new Date(Date.now() + h * 3600e3).toISOString();
function seed(api) {
  const now = new Date(), wib = new Date(now.getTime() + 7 * 3600e3), dow = (wib.getUTCDay() + 6) % 7;
  const monday = Date.UTC(wib.getUTCFullYear(), wib.getUTCMonth(), wib.getUTCDate() - dow) - 7 * 3600e3;
  const days = [...Array(7)].map((_, i) => ({ date: wibKey(new Date(monday + i * 864e5)), posts: [] }));
  const post = (over) => ({ id: "pl-1", candidate_id: "cand-a", job_id: "job-done", title: "Lompatan GILA", platform: "tiktok", platform_name: "TikTok",
    account_id: "acc-tt", account_handle: "imeclips", status: "planned", campaign: "ime-roleplay", campaign_name: "IME Roleplay", has_thumbnail: false,
    eligible: true, ineligible_reason: null, overdue: false, render: { state: "ready", label: "Final ready" }, ...over });
  const soon = hoursFromNow(2), todayIdx = days.findIndex((d) => d.date === wibKey(now));
  const later = days.findIndex((d) => d.date === wibKey(new Date(soon)));
  days[later].posts.push(post({ scheduled_for: soon }));
  const half = hoursFromNow(0.5);
  days[days.findIndex((d) => d.date === wibKey(new Date(half)))].posts.push(post({ id: "pl-2", platform: "youtube", platform_name: "YouTube Shorts", account_handle: "imeyt", scheduled_for: half,
    eligible: false, ineligible_reason: "Outside IME Roleplay week window", render: { state: "rendering", label: "Final rendering 40%", percent: 40 } }));
  api.schedule = { from: new Date(monday).toISOString(), now: now.toISOString(), days,
    posting_times: { tiktok: ["12:00", "19:00"], instagram: ["11:30"] },
    overdue: [post({ id: "pl-0", scheduled_for: hoursFromNow(-3), overdue: true, title: "Missed clip" })] };
  return { todayIdx };
}
async function open(app) {
  await app.locator('#flow [data-nav="schedule"]').click();
  await expect(app.locator("#scheduleSection")).toBeVisible();
  await expect(app.locator("#pageTitle")).toHaveText("Schedule");
  await expect(app.locator("#flow li.active .flow-label")).toHaveText("Schedule");
}

test("list: overdue on top, chips, free slots, actions", async ({ app, api }) => {
  seed(api);
  api.telegram = { ready: true, chat_id: "1", source: "user" };
  await open(app);
  const over = app.locator(".sday.is-overdue");
  await expect(over.locator("h3")).toHaveText("Overdue · 1");
  await expect(over.locator('[data-sched-row="pl-0"] .badge.failed').first()).toHaveText("Overdue");
  const r1 = app.locator('[data-sched-row="pl-1"]'), r2 = app.locator('[data-sched-row="pl-2"]');
  await expect(r1.locator("[data-render-state]")).toHaveText("Final ready");
  await expect(r2.locator("[data-render-state]")).toHaveText("Final rendering 40%");
  await expect(r2.locator("[data-render-state]")).toHaveClass(/failed/);           // not ready < 1 h before → red
  await expect(r2.locator(".badge.not-eligible")).toContainText("Outside IME Roleplay");
  await expect(r2.locator("[data-sched-send]")).toBeDisabled();
  await expect(app.locator(".sfree").first()).toContainText(/Free: TikTok 12:00 · 19:00|Nothing planned/);
  await r1.locator("[data-sched-send]").click();
  expect(api.calls.find((c) => c.path === "/api/publish/send-to-phone").body).toEqual({ candidate_id: "cand-a", platform: "tiktok" });
  await r1.locator("[data-sched-mark]").click();
  const f = app.locator('[data-sched-mark-form="pl-1"]');
  await f.locator("input").fill("http://x");
  await f.locator("button[type=submit]").click();
  await expect(f.locator(".account-msg")).toContainText("https://");
  await f.locator("input").fill("https://www.tiktok.com/@imeclips/video/7");
  await f.locator("button[type=submit]").click();
  await expect(r1).toHaveCount(0);
  expect(api.calls.filter((c) => c.method === "PATCH" && c.path === "/api/posts/pl-1").at(-1).body).toEqual({ status: "posted", url: "https://www.tiktok.com/@imeclips/video/7" });
  // phase 2: Drop = gone at once with Undo; the PATCH goes out after 5 s (Undo cancels it)
  await r2.locator("[data-sched-drop]").click();
  await expect(r2).toHaveCount(0);
  await app.click("#toastAction");                                                    // Undo
  await expect(r2).toHaveCount(1);
  expect(api.calls.some((c) => c.method === "PATCH" && c.path === "/api/posts/pl-2")).toBe(false);
  await r2.locator("[data-sched-drop]").click();
  await expect(r2).toHaveCount(0);
  await expect.poll(() => api.calls.filter((c) => c.method === "PATCH" && c.path === "/api/posts/pl-2").at(-1)?.body, { timeout: 8000 }).toEqual({ status: "dropped" });
});

test("reschedule opens the schedule sheet for that clip; week nav asks the next week", async ({ app, api }) => {
  seed(api);
  api.schedulePlan = { approved: true, status: "completed", blocking: [], campaign_name: null, platforms: [
    { platform: "tiktok", platform_name: "TikTok", times: [], accounts: [{ id: "acc-tt", handle: "imeclips", suggestions: [] }],
      post: { id: "pl-1", status: "planned", account_id: "acc-tt", scheduled_for: hoursFromNow(2) } }] };
  await open(app);
  await app.locator('[data-sched-row="pl-1"] [data-sched-replan]').click();
  await expect(app.locator("#scheduleSheet")).toHaveClass(/open/);
  await expect(app.locator("#scheduleSheetTitle")).toHaveText("Schedule");
  await app.keyboard.press("Escape");
  await app.click('[data-sched-week="1"]');
  await expect(app.locator("#schedWeekLabel")).toHaveText("Next week");
  const q = api.calls.filter((c) => c.path === "/api/schedule").at(-1);
  expect(q).toBeTruthy();
});

test("week calendar on desktop; list only on phones (screenshots)", async ({ app, api }) => {
  seed(api);
  await open(app);
  const mobile = test.info().project.name === "mobile";
  if (mobile) {
    await expect(app.locator(".sched-viewseg")).toBeHidden();
  } else {
    await app.click('[data-sched-view="week"]');
    await expect(app.locator(".sweek-day")).toHaveCount(7);
    await expect(app.locator(".sweek-post")).toHaveCount(2);
    await app.screenshot({ path: "test-results/schedule-week-1280.png" });
    await app.locator('.sweek-post[data-sched-open="pl-2"]').click();
    await expect(app.locator('[data-sched-row="pl-2"]')).toBeVisible();
  }
  expect(await app.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await app.screenshot({ path: `test-results/schedule-list-${mobile ? 390 : 1280}.png`, fullPage: true });
});

test("reminders (148): chip per row, banner when Telegram isn't set up, lead line when it is", async ({ app, api }) => {
  seed(api);
  const byId = Object.fromEntries(api.schedule.days.flatMap((d) => d.posts).map((p) => [p.id, p]));   // by id: after 22:00 WIB pl-1 is tomorrow
  byId["pl-1"].reminder_status = "sent"; byId["pl-2"].reminder_status = "no_chat"; api.schedule.overdue[0].reminder_status = "missed";
  api.schedule.telegram_ready = false; api.schedule.reminder_lead_min = 15;
  await open(app);
  await expect(app.locator('[data-sched-row="pl-1"] [data-reminder]')).toHaveText("Reminder sent");
  await expect(app.locator('[data-sched-row="pl-2"] [data-reminder]')).toHaveText("No reminder: add your Telegram chat in Account");
  await expect(app.locator('[data-sched-row="pl-0"] [data-reminder]')).toHaveText("Reminder missed (server was down)");
  await expect(app.locator(".sched-tg")).toContainText("isn't set up yet");
  api.schedule.telegram_ready = true;
  await app.evaluate(() => loadSchedule());   // UI phase 1 item 5: the menu's Refresh is gone
  await expect(app.locator(".sched-lead")).toHaveText("Telegram reminder 15 min before each post (Settings → Posting times).");
  await expect(app.locator(".sched-tg")).toHaveCount(0);
});

// UI phase 2, Schedule (owner 2026-10-14): one reminder line, neutral week arrows, Mark posted primary + Drop quiet,
// 9:16 thumbnails, past empty days on one line.
test("Schedule phase 2: buttons, thumbnails, week arrows, past empty days", async ({ app, api }) => {
  seed(api);
  const today = api.schedule.days.findIndex((d) => d.posts.length);
  await open(app);
  const row = app.locator("[data-sched-row]").first();
  await expect(row.locator("[data-sched-mark]")).toHaveClass(/primary/);
  await expect(row.locator("[data-sched-drop]")).toHaveClass(/quiet/);
  const t = await row.locator(".qthumb").boundingBox();
  expect(Math.round((t.height / t.width) * 9)).toBe(16);                          // 9:16
  expect(t.width).toBeGreaterThanOrEqual(56);
  for (const theme of ["light", "dark"]) { await app.evaluate((t) => window.applyTheme(t), theme);
  for (const b of await app.locator(".week-nav button").all()) {
    expect(await b.getAttribute("aria-pressed")).toBeNull();
    const bg = await b.evaluate((e) => getComputedStyle(e).backgroundColor);
    expect(bg).toMatch(/rgba\(0, 0, 0, 0\)|transparent/);                         // neutral, not the accent
  } }
  await expect(app.locator("#infoSchedule")).not.toContainText("Telegram");        // one reminder line: the list's own
});

test("Schedule phase 2: past days with nothing planned are one line", async ({ app, api }) => {
  seed(api);
  const base = new Date(api.schedule.days[0].date + "T12:00:00+07:00").getTime();
  api.schedule.days = [-3, -2, -1].map((n) => ({ date: wibKey(new Date(Date.now() + n * 864e5)), posts: [] }))
    .concat([{ date: wibKey(new Date()), posts: [] }]);
  await open(app);
  await expect(app.locator("[data-sched-past]")).toHaveCount(1);
  await expect(app.locator("[data-sched-past]")).toContainText("nothing planned");
  await expect(app.locator(".sday:not(.is-overdue):not(.sday-past)")).toHaveCount(1);   // just today
});
