// ClipFlow UI smoke tests. Base URL: CLIPFLOW_UI_BASE (default http://localhost, the nginx frontend).
// Default mode mocks every /api call (fixtures.js): deterministic, no API key, never creates a job.
// CLIPFLOW_UI_LIVE=1 also runs specs/live.spec.js read-only against the real backend.
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./specs",
  timeout: 30_000,
  expect: { timeout: 6_000 },
  fullyParallel: true,
  workers: process.env.CI ? 1 : 2, // modest: Lane A may be rendering on this box
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: ".report", open: "never" }]],
  use: {
    baseURL: process.env.CLIPFLOW_UI_BASE || "http://localhost",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, hasTouch: true } },
  ],
});
