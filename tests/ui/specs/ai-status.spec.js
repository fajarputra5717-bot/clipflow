// 220: Settings → AI & transcription starts with the provider chain (Gemini → Groq → Claude, "(no key)" when a key is
// missing), any forced provider, and who produced the caller's latest hooks.
const { test, expect } = require("../fixtures");

async function open(app, api, status) {
  api.user = { id: "u-a", username: "admin", role: "admin" };
  const g = (value) => ({ value, configured: true, source: "default", scope: "global" });
  api.settings = { CLIP_ANALYSIS_PROVIDER: g(status.analysis), TEXT_UTILITY_PROVIDER: g(status.utility),
    GROQ_MODEL_ANALYSIS: g("openai/gpt-oss-120b"), GROQ_MODEL_UTILITY: g("openai/gpt-oss-20b"), GEMINI_ANALYSIS_MODEL: g("gemini-3.6-flash") };
  await app.route("**/api/ai/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(status) }));
  await app.reload();
  await app.waitForResponse((r) => r.url().includes("/api/settings"));
  await app.locator('[data-nav="settings"] >> visible=true').first().click();
  await expect(app.locator("#settingsSheet")).toHaveClass(/open/);
}

test("AI group shows the chain, missing keys and the latest hooks' provider", async ({ app, api }) => {
  await open(app, api, { order: [{ name: "gemini", configured: true }, { name: "groq", configured: true }, { name: "claude", configured: false }],
    analysis: "auto", utility: "auto", last_hooks: { provider: "groq", at: "2026-10-14T07:40:00Z" } });
  const row = app.locator("#aiOrderRow");
  await expect(row.locator(".ai-chain")).toHaveText("Gemini → Groq → Claude (no key)");
  await expect(row).toContainText("Your latest hooks: Groq · 14 Oct, 14:40 WIB");
  await expect(app.locator('label[for="set-GROQ_MODEL_ANALYSIS"]')).toContainText("Groq model, clip analysis");
  await expect(app.locator("#set-CLIP_ANALYSIS_PROVIDER")).toHaveValue("auto");
});

test("forced provider and no hooks yet", async ({ app, api }) => {
  await open(app, api, { order: [{ name: "gemini", configured: true }, { name: "groq", configured: true }, { name: "claude", configured: true }],
    analysis: "groq", utility: "auto", last_hooks: null });
  await expect(app.locator("#aiOrderRow")).toContainText("Clip analysis: forced to Groq · No hooks yet");
});
