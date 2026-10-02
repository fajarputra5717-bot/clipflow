// QA (Lane C) P1 gate: each built step vs the flow-preview mock, 1280 + 390. Screenshots + DOM facts.
const { test, expect, nav } = require("../fixtures");
const OUT = (process.env.QA_SHOTS || "test-results");
const facts = (p) => p.evaluate(() => ({
  title: document.querySelector("#pageTitle")?.innerText,
  flow: [...document.querySelectorAll("#flow li")].map((l) => l.innerText.replace(/\s+/g, " ").trim() + (l.querySelector(":disabled") ? " [off]" : "")),
  money: (document.body.innerText.match(/\$\s?\d|USD|Rp\s?\d/g) || []).slice(0, 5),
}));
test("built steps vs mock", async ({ app, page, browser }, info) => {
  const p = info.project.name, shot = (n) => page.screenshot({ path: `${OUT}/app-${p}-${n}.png` });
  await expect(app.locator("#flow")).toBeVisible({ timeout: 8000 });
  await shot("1-analyze"); console.log("ANALYZE", p, JSON.stringify(await facts(page)));
  await nav(app, "queue"); await page.waitForTimeout(400); await shot("2-review-list");
  await app.locator('[data-queue-open="job-done"]').click(); await page.waitForTimeout(600);
  await shot("3-review-detail"); console.log("REVIEW", p, JSON.stringify(await facts(page)));
  const chips = await app.locator("#candidate-cand-a").innerText(); console.log("CAND-A", p, JSON.stringify(chips.replace(/\s+/g, " ").slice(0, 400)));
  await app.locator("#candidate-cand-a [data-edit]").first().click(); await page.waitForTimeout(700);
  await app.locator("#candidate-cand-a").scrollIntoViewIfNeeded(); await shot("4-editor"); console.log("EDITOR", p, JSON.stringify(await facts(page)));
  const tabs = await app.locator("#candidate-cand-a [data-edit-tab]").allInnerTexts(); console.log("TABS", p, JSON.stringify(tabs));
  const m = await (await browser.newContext({ viewport: page.viewportSize(), reducedMotion: "reduce" })).newPage();
  await m.goto((process.env.CLIPFLOW_UI_BASE || "http://localhost") + "/flow-preview.html");
  for (const s of ["analyze", "review", "editor", "campaign"]) { const b = m.locator(`[data-step="${s}"]`).first(); if (await b.count()) { await b.click(); await m.waitForTimeout(400); } await m.screenshot({ path: `${OUT}/mock-${p}-${s}.png` }); }
});
