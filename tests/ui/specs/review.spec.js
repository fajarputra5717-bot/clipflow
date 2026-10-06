// Review page (lane B, P4 task 6): flow-preview step 4 as its own view, #review/<jobId>. Mock mode.
const { test, expect, job, candidate } = require("../fixtures");

const ok = (id, label) => ({ id, ok: true, blocking: true, label, detail: "", fix: null });
function reviewJob() {
  const j = job({ id: "job-rv", status: "review", source_title: "Citer Molotov Ketemu KDM", campaign: "ime-roleplay" });
  j.candidates = [
    candidate(j.id, { id: "c63", clip_index: 0, score: 63, ai_title: "Lowest", rule_checks: [ok("length", "Length 39 s"),
      { id: "watermark", ok: false, blocking: true, label: "Campaign watermark missing", detail: "", fix: "rerender" }] }),
    candidate(j.id, { id: "c94", clip_index: 1, score: 94, ai_title: "Best", reason: "Reaksi panik lalu tawa, ditutup tebakan lucu.",
      rule_checks: [ok("length", "Length 40 s"), ok("hashtags", "Hashtags")] }),
    candidate(j.id, { id: "c88", clip_index: 2, score: 88, ai_title: "Too long", start_time: 6, end_time: 102,
      rule_checks: [{ id: "length", ok: false, blocking: true, label: "Length 96 s: too long for Facebook Reels (3–90 s)", detail: "", fix: "trim", fix_target: 88 }] }),
    candidate(j.id, { id: "c71", clip_index: 3, score: 71, ai_title: "No tags",
      rule_checks: [{ id: "hashtags", ok: false, blocking: true, label: "Hashtags missing or out of order", detail: "", fix: "hashtags" },
                    { id: "safety", ok: false, blocking: false, label: "Content check: 1 possible issue", detail: "", fix: "dismiss" }] }),
  ];
  return j;
}

async function openReview(app, api, j = reviewJob()) {
  api.queue = [j, job({ id: "job-other", status: "review", source_title: "Second video" })];
  api.jobs[j.id] = j;
  api.jobs["job-other"] = { ...api.queue[1], candidates: [candidate("job-other", { id: "o1", score: 50, ai_title: "Other clip" })] };
  await app.evaluate((id) => { location.hash = `#review/${id}`; }, j.id);
  await expect(app.locator(".rv-clip .rv-ctitle").first()).toBeVisible();
}

test.describe("Review page", () => {
  test("header, sorted by hook score, chips, hints, approve gate", async ({ app, api }) => {
    await openReview(app, api);
    await expect(app.locator(".rv-eyebrow")).toHaveText("Step 4 · Review");
    await expect(app.locator(".rv-title")).toHaveText("Citer Molotov Ketemu KDM");
    await expect(app.locator(".rv-desc")).toHaveText("Clips are sorted by hook score. A clip can be scheduled only when every campaign rule passes.");
    await expect(app.locator("#rvCount")).toHaveText("4 to review");
    await expect(app.locator(".rv-score")).toHaveText(["Hook 94", "Hook 88", "Hook 71", "Hook 63"]);
    await expect(app.locator(".rv-reason b").first()).toHaveText("Reaksi panik lalu tawa");
    await expect(app.locator(".rv-fix")).toHaveText(["Trim to 88 s", "Add tags", "Dismiss", "Fix watermark"]);
    await expect(app.locator(".rv-hint")).toHaveText(["All campaign rules pass.", "Fix 1 rule to approve.", "Fix 1 rule to approve.", "Fix 1 rule to approve."]);
    await expect(app.locator("[data-rv-approve]")).toHaveCount(4);
    expect(await app.locator("[data-rv-approve]").evaluateAll((b) => b.map((x) => !x.disabled))).toEqual([true, false, false, false]);
    await expect(app.locator(".rv-time").nth(1)).toHaveText("1:36");
    await expect(app.locator(".rv-open").first()).toHaveAttribute("href", "#editor/job-rv/c94");
  });

  test("grid: 2 columns on desktop, 1 on mobile; no horizontal scroll", async ({ app, api }, info) => {
    await openReview(app, api);
    const cols = await app.locator("#rvGrid").evaluate((g) => getComputedStyle(g).gridTemplateColumns.split(" ").length);
    expect(cols).toBe(info.project.name === "mobile" ? 1 : 2);
    expect(await app.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });

  test("quick fixes call the right endpoints", async ({ app, api }) => {
    await openReview(app, api);
    await app.locator(".rv-fix", { hasText: "Trim to 88 s" }).click();
    await expect.poll(() => api.calls.find((c) => c.method === "PUT" && c.path.endsWith("/c88/editor/fix-length"))?.body).toEqual({ target: 88 });
    await app.locator(".rv-fix", { hasText: "Add tags" }).click();
    await expect.poll(() => api.calls.find((c) => c.method === "POST" && c.path.endsWith("/c71/fix-rule"))?.body).toEqual({ rule: "hashtags" });
    await app.locator(".rv-fix", { hasText: "Fix watermark" }).click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path.endsWith("/c63/regenerate-preview"))).toBe(true);
    await app.locator("[data-rv-approve]").first().click();
    await expect.poll(() => api.calls.some((c) => c.method === "POST" && c.path.endsWith("/c94/approve"))).toBe(true);
  });

  test("job picker lists jobs and switches the grid", async ({ app, api }) => {
    await openReview(app, api);
    await app.locator("[data-rv-pick]").click();
    await expect(app.locator(".rv-opt")).toHaveCount(2);
    await app.locator('[data-rv-job="job-other"]').click();
    await expect(app.locator(".rv-title")).toHaveText("Second video");
    await expect(app.locator(".rv-ctitle")).toHaveText(["Other clip"]);
    await expect(app).toHaveURL(/#review\/job-other$/);
  });
});
