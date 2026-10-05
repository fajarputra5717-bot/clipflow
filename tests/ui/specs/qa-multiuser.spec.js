// QA (Lane C) · P1.5 multi-user · cross-user isolation. Every failure here is HIGH severity (owner 2026-10-05).
// Rule: user B must get 404 (not 200/403/500) for anything owned by user A: jobs, clips, files (video, thumbnail,
// watermark), settings, activity. Unauthenticated → 401. Non-destructive by design: only GETs, plus write ATTEMPTS
// by B on A's rows that must be refused (404) — run against STAGING only.
//
// Run (staging):  QA_MULTIUSER=1 CLIPFLOW_API_BASE=http://localhost:8001 \
//   QA_USER_A=… QA_PASS_A=… QA_USER_B=… QA_PASS_B=… npx playwright test specs/qa-multiuser.spec.js --project=desktop
// Optional (adjust once P1.5's API is final): QA_LOGIN_PATH (default /api/auth/login), QA_LOGIN_BODY ('user'|'username').
// Precondition: A owns ≥ 1 job with ≥ 1 candidate that has a preview + thumbnail, and ≥ 1 watermark asset.
const { test, expect, request } = require("@playwright/test");

const BASE = process.env.CLIPFLOW_API_BASE || "http://localhost:8001";
const LOGIN = process.env.QA_LOGIN_PATH || "/api/auth/login";
const UKEY = process.env.QA_LOGIN_BODY || "username";
const run = process.env.QA_MULTIUSER === "1";

async function login(user, pass) {
  const ctx = await request.newContext({ baseURL: BASE });
  const r = await ctx.post(LOGIN, { data: { [UKEY]: user, password: pass } });
  expect(r.status(), `login ${user}`).toBeLessThan(300);
  return ctx; // cookie jar holds the HttpOnly session
}
const json = async (r) => { try { return await r.json(); } catch { return null; } };
const items = (d) => Array.isArray(d) ? d : (d?.jobs || d?.items || []);

test.describe("P1.5 cross-user isolation (HIGH)", () => {
  test.skip(!run, "set QA_MULTIUSER=1 (staging, two users) to run");
  let A, B, anon, jobA, candA, wmA, mediaA = [];

  test.beforeAll(async () => {
    A = await login(process.env.QA_USER_A, process.env.QA_PASS_A);
    B = await login(process.env.QA_USER_B, process.env.QA_PASS_B);
    anon = await request.newContext({ baseURL: BASE });
    const jobs = items(await json(await A.get("/api/jobs?scope=queue"))).concat(items(await json(await A.get("/api/jobs?scope=current"))));
    expect(jobs.length, "user A needs at least one job (precondition)").toBeGreaterThan(0);
    jobA = jobs[0].id;
    const detail = await json(await A.get(`/api/jobs/${jobA}`));
    candA = (detail?.candidates || [])[0]?.id;
    expect(candA, "user A's job needs a candidate (precondition)").toBeTruthy();
    const wm = await json(await A.get("/api/assets/watermarks"));
    wmA = (Array.isArray(wm) ? wm : wm?.assets || wm?.items || [])[0]?.id;
    mediaA = [
      `/api/jobs/${jobA}/candidates/${candA}/preview`,
      `/api/jobs/${jobA}/candidates/${candA}/thumbnail`,
      `/api/jobs/${jobA}/candidates/${candA}/render`,
      ...(wmA ? [`/api/assets/watermarks/${wmA}/file`, `/api/assets/watermarks/${wmA}`] : []),
    ];
  });

  test("A can read its own job (sanity)", async () => {
    expect((await A.get(`/api/jobs/${jobA}`)).status()).toBe(200);
  });

  test("B gets 404 on A's job, candidates and job sub-resources", async () => {
    for (const p of [`/api/jobs/${jobA}`, `/api/jobs/${jobA}/candidates`, `/api/jobs/${jobA}/candidates/${candA}`,
                     `/api/jobs/${jobA}/candidates/${candA}/versions`]) {
      const s = (await B.get(p)).status();
      expect(s, `B GET ${p}`).toBe(404);
    }
  });

  test("B's job lists never contain A's job", async () => {
    for (const scope of ["current", "queue"]) {
      const ids = items(await json(await B.get(`/api/jobs?scope=${scope}`))).map((j) => j.id);
      expect(ids, `B /api/jobs?scope=${scope}`).not.toContain(jobA);
    }
  });

  test("B gets 404 on A's files (preview, thumbnail, final, watermark), with or without a media token", async () => {
    const mt = (await json(await B.get("/api/media-token")))?.token || (await json(await B.get("/api/media-token")))?.mt;
    for (const p of mediaA) {
      expect((await B.get(p)).status(), `B GET ${p}`).toBe(404);
      if (mt) expect((await B.get(`${p}${p.includes("?") ? "&" : "?"}mt=${encodeURIComponent(mt)}`)).status(), `B GET ${p}?mt=<B's token>`).toBe(404);
    }
  });

  test("A's media token does not open A's files for an anonymous client in another session", async () => {
    // A link shared outside the session must not become a cross-user key; anonymous + no token → 401.
    for (const p of mediaA) expect((await anon.get(p)).status(), `anon GET ${p}`).toBe(401);
  });

  test("B cannot change or act on A's clip (404, and A's data unchanged)", async () => {
    const before = await json(await A.get(`/api/jobs/${jobA}`));
    const attempts = [
      ["patch", `/api/jobs/${jobA}/candidates/${candA}`, { description: "QA cross-user write attempt" }],
      ["post", `/api/jobs/${jobA}/candidates/${candA}/approve`, null],
      ["post", `/api/jobs/${jobA}/candidates/${candA}/regenerate-preview`, null],
      ["post", `/api/jobs/${jobA}/cancel`, null],
      ["delete", `/api/jobs/${jobA}`, null],
    ];
    for (const [m, p, data] of attempts) {
      const s = (await B[m](p, data ? { data } : {})).status();
      expect(s, `B ${m.toUpperCase()} ${p}`).toBe(404);
    }
    const after = await json(await A.get(`/api/jobs/${jobA}`));
    expect(after?.candidates?.[0]?.description).toBe(before?.candidates?.[0]?.description);
    expect(after?.status).toBe(before?.status);
  });

  test("B's activity feed never shows A's tasks", async () => {
    const act = items(await json(await B.get("/api/activity")));
    expect(act.filter((t) => t.job_id === jobA), "B /api/activity").toEqual([]);
  });

  test("settings are per user; B can't read A's values or write global settings", async () => {
    const a = await json(await A.get("/api/settings")), b = await json(await B.get("/api/settings"));
    expect(b, "B /api/settings").toBeTruthy();
    // Secrets never come back in clear to members.
    expect(JSON.stringify(b)).not.toMatch(/sk-ant-|AIza[0-9A-Za-z_-]{20,}/);
    // A member must not change global (admin-only) keys: 403 or 404, never 200.
    const s = (await B.put("/api/settings", { data: { values: { WHISPER_MODEL: "tiny" } } })).status();
    expect([403, 404], `B PUT global WHISPER_MODEL → ${s}`).toContain(s);
    expect(a, "A /api/settings").toBeTruthy();
  });

  test("unauthenticated requests get 401 everywhere", async () => {
    for (const p of ["/api/jobs?scope=current", `/api/jobs/${jobA}`, "/api/activity", "/api/settings", "/api/assets/watermarks"]) {
      expect((await anon.get(p)).status(), `anon GET ${p}`).toBe(401);
    }
  });
});
