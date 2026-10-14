// QA (Lane C) · automated end-to-end check, STAGING ONLY.
// One command: tests/qa/e2e/run.sh   (see README.md for env knobs)
// Pipeline: import (UI) → analyze → review → editor (caption, audio edit, render preview) → approve/final render →
// publish list (dry run: nothing is posted) + 2 concurrent imports with the island "+N" list, shimmer/glow shots,
// phone-emulated editor checks, loudness of the rendered clips (ffmpeg ebur128 inside the staging worker).
// Safety: refuses any base URL that isn't localhost/127.0.0.1 :8080/:8001, any user that isn't lane-c-*, waits for an
// idle queue, only touches the jobs it creates (deleted at the end unless E2E_KEEP=1).
const fs = require("fs"), path = require("path"), { execFileSync, spawnSync } = require("child_process");
const PW = process.env.PW_MODULE || "/opt/clipflow/tests/ui/node_modules/playwright";
const { chromium } = require(PW);

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8080";
const URL_ = process.env.E2E_URL || "https://www.youtube.com/watch?v=npDdITTUgl8";   // real video (4 m 44 s), already cached on staging (no pot sidecar there)
const USER = process.env.E2E_USER || "lane-c-a";
const KEEP = process.env.E2E_KEEP === "1";
const SKIP_FINAL = process.env.E2E_SKIP_FINAL === "1";
const RESUME = process.env.E2E_JOB || "";                // debug: reuse an existing lane-c job instead of importing
const OUT = process.env.E2E_OUT || path.join(__dirname, "runs", new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19));
const WORKER = "clipflow-staging-worker-1", PG = "clipflow-staging-postgres-1";
const TS = Date.now().toString(36);

(function assertSafe() {
  const u = new URL(BASE);
  if (!["localhost", "127.0.0.1"].includes(u.hostname) || !["8080", "8001"].includes(u.port)) throw new Error(`e2e REFUSES ${BASE}: staging only (localhost:8080/:8001)`);
  if (!/^lane-c-/.test(USER)) throw new Error(`e2e REFUSES user ${USER}: only lane-c-* accounts`);
})();
function password() {
  if (process.env.E2E_PASS) return process.env.E2E_PASS;
  const f = process.env.QA_USERS_FILE || "";
  if (f && fs.existsSync(f)) { const v = JSON.parse(fs.readFileSync(f, "utf8"))[USER]; return typeof v === "object" ? v.password : v; }
  throw new Error("no password: set QA_USERS_FILE (json {user: password}) or E2E_PASS");
}
const sh = (cmd, args) => execFileSync(cmd, args, { encoding: "utf8", maxBuffer: 20e6 }).trim();
const psql = (sql) => sh("docker", ["exec", PG, "psql", "-U", "clipflow", "-d", "clipflow", "-tAc", sql]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
const shot = (name) => path.join(OUT, `${name}.png`);

const steps = []; const times = {}; const notes = [];
async function step(name, fn, needs) {
  if (needs && steps.find((s) => s.name === needs)?.status !== "PASS") { steps.push({ name, status: "SKIP", note: `needs "${needs}"` }); return; }
  const t0 = Date.now();
  try { const note = await fn(); steps.push({ name, status: "PASS", secs: (Date.now() - t0) / 1000, note: note || "" }); }
  catch (e) { steps.push({ name, status: "FAIL", secs: (Date.now() - t0) / 1000, note: String(e.message || e).split("\n")[0].slice(0, 300) }); }
  const s = steps[steps.length - 1]; console.log(`${s.status.padEnd(4)} ${name}${s.secs ? ` (${s.secs.toFixed(1)} s)` : ""}${s.note ? " — " + s.note : ""}`);
}
function loud(containerPath) {
  const a = sh("docker", ["exec", WORKER, "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", containerPath]);
  const dur = parseFloat(sh("docker", ["exec", WORKER, "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", containerPath]));
  const r = spawnSync("docker", ["exec", WORKER, "ffmpeg", "-hide_banner", "-nostats", "-i", containerPath, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], { encoding: "utf8", maxBuffer: 50e6 });
  const out = (r.stdout || "") + (r.stderr || "");
  const sum = out.slice(out.lastIndexOf("Summary:"));
  const num = (re) => { const m = sum.match(re); return m ? parseFloat(m[1]) : null; };
  return { audio: !!a, dur, lufs: num(/I:\s+(-?[\d.]+) LUFS/), lra: num(/LRA:\s+(-?[\d.]+) LU/), tp: num(/Peak:\s+(-?[\d.]+) dBFS/) };
}
const fmt = (l) => `${l.lufs} LUFS, TP ${l.tp} dBTP, ${l.dur.toFixed(1)} s`;

(async () => {
  console.log(`e2e → ${BASE} as ${USER}; artifacts in ${OUT}`);
  const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
  const ctxs = [];
  async function newCtx(label, opts = {}) {
    const vdir = path.join(OUT, "video", label); fs.mkdirSync(vdir, { recursive: true });
    const ctx = await browser.newContext({ baseURL: BASE, extraHTTPHeaders: { "X-Real-IP": `10.99.77.${10 + ctxs.length}` }, recordVideo: { dir: vdir, size: { width: Math.min(opts.viewport?.width || 1280, 1280), height: Math.min(opts.viewport?.height || 800, 800) } }, ...opts });
    await ctx.tracing.start({ screenshots: true, snapshots: true });
    const r = await ctx.request.post("/api/auth/login", { data: { username: USER, password: password() } });
    if (!r.ok()) throw new Error(`login ${r.status()}`);
    ctxs.push([label, ctx]); return ctx;
  }
  const api = async (ctx, method, p, data) => { const r = await ctx.request.fetch(p, { method, data }); let j = null; try { j = await r.json(); } catch {} return { s: r.status(), j }; };
  const jobs = []; let jobId = RESUME, secondId = "", cid = "", ctxMain, page;
  const pr = {};    // paths + measures

  // --- 0. idle queue
  await step("0 staging queue idle", async () => {
    for (let i = 0; i < 120; i++) {
      const busy = parseInt(psql("select (select count(*) from jobs where status not in ('completed','review','failed','cancelled','purged','partial_failure')) + (select count(*) from clip_candidates where status not in ('review','completed','failed','cancelled'))"), 10);
      if (!busy) return "idle"; await sleep(10000);
    } throw new Error("queue not idle after 20 min");
  });
  ctxMain = await newCtx("main", { viewport: { width: 1280, height: 800 } }); page = await ctxMain.newPage();
  const errs = []; page.on("pageerror", (e) => errs.push(String(e).slice(0, 100)));

  // --- 1. import (UI)
  async function importViaUi(pg, title) {
    await pg.goto("/#analyze"); await pg.waitForSelector("#youtubeUrl"); await pg.fill("#youtubeUrl", URL_);
    const det = pg.locator("#importOptions"); if (await det.count() && !(await det.evaluate((e) => e.open))) await det.locator("summary").click();
    await pg.fill("#jobCustomTitle", title).catch(() => {}); await pg.click('[data-clips="2"]').catch(() => {});
    await pg.waitForFunction(() => !document.getElementById("analyzeButton").disabled, null, { timeout: 8000 });
    await pg.click("#analyzeButton"); await sleep(1500);
    for (let i = 0; i < 20; i++) { const j = (await api(pg.context(), "GET", "/api/jobs")).j; const list = Array.isArray(j) ? j : j?.jobs || []; const f = list.find((x) => (x.custom_title || x.title || "") === title); if (f) return f.id; await sleep(1000); }
    throw new Error("job not listed after start");
  }
  const tImport = Date.now();
  if (!RESUME) await step("1 import (UI, real YouTube video)", async () => { jobId = await importViaUi(page, `e2e-main-${TS}`); jobs.push(jobId); await page.screenshot({ path: shot("01-import-started") }); return `job ${jobId.slice(0, 8)}`; });
  else steps.push({ name: "1 import (UI, real YouTube video)", status: "SKIP", note: `resuming ${RESUME}` });

  // --- 2. second import at once + island +N list
  if (!RESUME) await step("2 second import at once; island +N list shows both and updates", async () => {
    const p2 = await ctxMain.newPage(); secondId = await importViaUi(p2, `e2e-second-${TS}`); jobs.push(secondId); await p2.close();
    await page.goto("/#analyze"); await sleep(4000);
    await page.locator("#island").click(); await sleep(1200);
    const read = () => page.evaluate(() => { const o = document.getElementById("jobOverlay"); const s = getComputedStyle(o); return { visible: s.visibility === "visible" && s.opacity !== "0", text: (o.innerText || "").replace(/\s+/g, " ").trim() }; });
    const a = await read(); await page.screenshot({ path: shot("02-island-plusN-list") });
    if (!a.visible) throw new Error("island list did not open");
    const both = a.text.includes(`e2e-main-${TS}`) && a.text.includes(`e2e-second-${TS}`);
    if (!both) throw new Error(`list text lacks both jobs: ${a.text.slice(0, 160)}`);
    let b = a, waited = 0;   // live update: wait (≤ 4 min) until any row text changes (download → transcribing step)
    while (waited < 240 && b.text === a.text) { await sleep(10000); waited += 10; b = await read(); if (!b.visible) { await page.locator("#island").click(); await sleep(800); b = await read(); } }
    await page.screenshot({ path: shot("02-island-plusN-list-later") });
    if (b.text === a.text) throw new Error(`list never changed in ${waited} s: «${a.text.slice(0, 120)}»`);
    return `both listed; live update after ${waited} s: «${a.text.slice(0, 100)}» → «${b.text.slice(0, 100)}»`;
  }, "1 import (UI, real YouTube video)");

  // --- 3. shimmer/glow screenshots on the running job at 1440 and 390
  await step("3 shimmer/glow screenshots (1440, 390)", async () => {
    const out = [];
    for (const [w, h] of [[1440, 900], [390, 844]]) {
      const c = await newCtx(`shimmer-${w}`, { viewport: { width: w, height: h } }); const p = await c.newPage();
      await p.goto("/#analyze"); await sleep(3500);
      const info = await p.evaluate(() => { const card = document.querySelector(".job-card.is-running"); const an = document.getAnimations().filter((a) => a.playState === "running").map((a) => a.animationName || a.transitionProperty).filter(Boolean); return { running: !!card, anims: [...new Set(an)].slice(0, 8) }; });
      await p.screenshot({ path: shot(`03-running-job-${w}`) });
      const card = p.locator(".job-card.is-running").first(); if (await card.count()) await card.screenshot({ path: shot(`03-running-card-${w}`) });
      out.push(`${w}: card running=${info.running}, animations ${JSON.stringify(info.anims)}`);
      if (!info.running) throw new Error(`no running job card at ${w} (${out.join("; ")})`);
      await c.tracing.stop({ path: path.join(OUT, `trace-shimmer-${w}.zip`) }).catch(() => {}); await c.close(); ctxs.pop();
    } return out.join("; ");
  }, RESUME ? "__resume__" : "1 import (UI, real YouTube video)");

  // --- drop the second import (it only existed for the +N check)
  if (secondId) { await api(ctxMain, "POST", `/api/jobs/${secondId}/cancel`).catch(() => {}); await sleep(3000); }

  // --- 4. analyze → review
  await step("4 analyze → review (time per stage)", async () => {
    const t0 = Date.now(); let last = "";
    for (let i = 0; i < 360; i++) {   // ≤ 60 min
      const j = (await api(ctxMain, "GET", `/api/jobs/${jobId}`)).j; const st = `${j.status}|${j.progress}|${j.message || ""}`;
      if (st !== last) { last = st; console.log(`   job ${j.status} ${j.progress}% ${j.message || ""}`); }
      if (["review", "completed"].includes(j.status)) break; if (["failed", "cancelled"].includes(j.status)) throw new Error(`job ${j.status}: ${j.error_message || j.message}`);
      await sleep(10000);
    }
    times.analyze_s = (Date.now() - (RESUME ? t0 : tImport)) / 1000;
    const cs = (await api(ctxMain, "GET", `/api/jobs/${jobId}/candidates`)).j; if (!cs.length) throw new Error("no clips");
    cid = cs.sort((a, b) => (b.score || 0) - (a.score || 0))[0].id;
    let line = ""; try { line = sh("docker", ["logs", "--since", new Date(tImport - 60000).toISOString(), WORKER]).split("\n").reverse().find((l) => l.includes(`Stage timings job ${jobId}`)) || ""; } catch {}
    notes.push(`stage timings (worker log): ${line.replace(/^\[.*?\]\s*/, "").slice(0, 400) || "n/a"}`);
    return `import→review ${(times.analyze_s / 60).toFixed(1)} min, ${cs.length} clips`;
  }, RESUME ? null : "1 import (UI, real YouTube video)");

  // --- 5. review page
  await step("5 review page lists the clip, opens the editor", async () => {
    await page.goto("/#review"); await sleep(2500); await page.screenshot({ path: shot("05-review") });
    let a = page.locator(`a.rv-open[href*="${cid}"]`);
    if (!(await a.count())) { await page.locator('.rv-seg button:has-text("All")').first().click().catch(() => {}); await sleep(1500); a = page.locator(`a.rv-open[href*="${cid}"]`); }
    if (!(await a.count())) throw new Error("clip row not in the review list (even under All)");
    await a.first().evaluate((e) => { const d = e.closest("details.rv-more"); if (d) d.open = true; }); await a.first().click(); await page.waitForSelector("#edVideo", { timeout: 15000 }); await sleep(2000); await page.screenshot({ path: shot("05-editor-open") });
    const row = psql(`select preview_path from clip_candidates where id='${cid}'`); pr.previewA = row; pr.A = loud(row); return `baseline preview ${fmt(pr.A)}`;
  }, "4 analyze → review (time per stage)");

  // --- 6. editor: caption, audio edit, render preview
  await step("6 editor: change caption, toggle audio edit, render preview", async () => {
    const cap = page.locator("#edCapText"); await cap.waitFor({ timeout: 8000 }); const before = await cap.inputValue();
    await cap.fill(`E2E CAPTION ${TS}`); await sleep(800);
    await page.locator('[data-ed-tab="audio"]').click(); await sleep(600);
    const flips = [];   // two audio edits that always have an effect on a clip with speech: Loud & punchy + Light compression
    for (const sel of ["[data-ed-loud]", "[data-ed-compress]"]) { const sw = page.locator(sel); const was = await sw.getAttribute("aria-checked"); await sw.click(); await sleep(700); const now = await sw.getAttribute("aria-checked"); if (now === was) throw new Error(`${sel} did not change`); flips.push(`${sel.replace(/\[data-ed-|\]/g, "")} ${was}→${now}`); }
    const was = flips.join(", "), now = "";
    pr.editWas = was; await page.screenshot({ path: shot("06-editor-edited") });
    const t0 = Date.now(); await page.locator("[data-ed-render]").click();
    for (let i = 0; i < 120; i++) { await sleep(3000); const c = (await api(ctxMain, "GET", `/api/jobs/${jobId}/candidates`)).j.find((x) => x.id === cid); if (i > 1 && c.status === "review") break; if (c.status === "failed") throw new Error("preview failed"); if (i === 119) throw new Error("preview not done in 6 min"); }
    times.preview_s = (Date.now() - t0) / 1000; await sleep(1500);
    const rowB = psql(`select preview_path from clip_candidates where id='${cid}'`); pr.B = loud(rowB);
    const txt = psql(`select coalesce(subtitle_text,'')||'|'||coalesce(subtitle_override,'') from clip_candidates where id='${cid}'`);
    await page.screenshot({ path: shot("06-editor-after-preview") });
    const captionSaved = txt.toUpperCase().includes(`E2E CAPTION ${TS}`.toUpperCase());
    const changed = Math.abs((pr.B.lufs ?? 0) - (pr.A.lufs ?? 0)) >= 0.2 || Math.abs((pr.B.lra ?? 0) - (pr.A.lra ?? 0)) >= 0.4 || Math.abs((pr.B.tp ?? 0) - (pr.A.tp ?? 0)) >= 0.2 || Math.abs(pr.B.dur - pr.A.dur) > 0.15;
    if (!captionSaved) throw new Error(`caption text not stored (db: ${txt.slice(0, 80)})`);
    if (!changed) throw new Error(`audio edits did not change the render: A ${fmt(pr.A)} LRA ${pr.A.lra} / B ${fmt(pr.B)} LRA ${pr.B.lra}`);
    return `preview render ${times.preview_s.toFixed(0)} s; audio edits (${was}); A ${fmt(pr.A)}, LRA ${pr.A.lra} → B ${fmt(pr.B)}, LRA ${pr.B.lra}; caption stored`;
  }, "5 review page lists the clip, opens the editor");

  // --- 7. final render
  await step("7 approve → final render, sound present", async () => {
    await page.locator('[data-ed-tab="export"]').click(); await sleep(800);
    const t0 = Date.now(); await page.locator("[data-ed-approve]").click(); await sleep(1500);
    const dlg = page.locator("button:has-text('Approve'):visible").last(); // confirm if a sheet appears
    for (let i = 0; i < 200; i++) { await sleep(3000); const c = (await api(ctxMain, "GET", `/api/jobs/${jobId}/candidates`)).j.find((x) => x.id === cid); if (c.status === "completed") break; if (c.status === "failed") throw new Error(`final failed: ${c.error_message}`); if (i === 199) throw new Error("final not done in 10 min"); }
    times.final_s = (Date.now() - t0) / 1000;
    const fp = psql(`select final_path from clip_candidates where id='${cid}'`); pr.F = loud(fp);
    await page.screenshot({ path: shot("07-final-done") });
    if (!pr.F.audio) throw new Error("final has no audio stream"); if (pr.F.lufs === null || pr.F.lufs < -30) throw new Error(`final too quiet / silent: ${fmt(pr.F)}`);
    if (pr.F.tp > -0.9) throw new Error(`true peak too hot: ${fmt(pr.F)}`);
    return `final render ${times.final_s.toFixed(0)} s; final ${fmt(pr.F)} (preview B ${pr.B.lufs} LUFS)`;
  }, SKIP_FINAL ? "__skip_final__" : "6 editor: change caption, toggle audio edit, render preview");

  // --- 8. publish list (dry run)
  await step("8 publish list shows the clip (dry run, nothing posted)", async () => {
    const q = `select count(*) from clip_posts where candidate_id='${cid}' and status in ('posted','claimed','paid')`; const before = parseInt(psql(q), 10);
    await page.goto("/#publish"); await sleep(3000); await page.screenshot({ path: shot("08-publish") });
    const posted = parseInt(psql(q), 10); if (posted !== before) throw new Error("a post was marked posted during the run: dry run violated");
    const txt = await page.evaluate(() => document.body.innerText); const el = await page.locator("#publishList").count();
    return `publish page rendered (${el ? "list present" : "no #publishList"}); no post marked posted by this run`;
  }, SKIP_FINAL ? null : "7 approve → final render, sound present");

  // --- 9. phone emulation
  await step("9 phone (390×844, touch): editor mute, scrub, toggles", async () => {
    const c = await newCtx("phone", { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 }); const p = await c.newPage();
    await p.goto(`/#editor/${jobId}/${cid}`); await p.waitForSelector("#edVideo", { timeout: 15000 }); await sleep(2500);
    const V = () => p.evaluate(() => { const v = document.getElementById("edVideo"); return { t: +v.currentTime.toFixed(2), muted: v.muted, dur: v.duration }; });
    const m0 = (await V()).muted; await p.locator("[data-ed-mute]").tap(); await sleep(300); const m1 = (await V()).muted; if (m0 === m1) throw new Error("mute button did not toggle");
    await p.locator("[data-ed-mute]").tap(); await sleep(300);
    await p.evaluate(() => document.getElementById("edVideo").pause()); const sb = await p.locator("[data-ed-scrub]").boundingBox(); await p.touchscreen.tap(sb.x + sb.width * 0.5, sb.y + sb.height / 2); await sleep(600);
    const s = await V(); if (Math.abs(s.t - s.dur / 2) > s.dur * 0.08) throw new Error(`scrub tap landed at ${s.t}/${s.dur}`);
    await p.locator('[data-ed-tab="audio"]').tap(); await sleep(600); const sw = p.locator("[data-ed-compress]"); const a0 = await sw.getAttribute("aria-checked"); await sw.tap(); await sleep(500); const a1 = await sw.getAttribute("aria-checked"); if (a0 === a1) throw new Error("audio switch did not toggle by touch"); await sw.tap(); await sleep(500);
    const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth); await p.screenshot({ path: shot("09-phone-editor") });
    if (ov > 1) throw new Error(`horizontal overflow ${ov}px`);
    await c.tracing.stop({ path: path.join(OUT, "trace-phone.zip") }).catch(() => {}); await c.close(); ctxs.pop();
    return `mute ${m0}→${m1}→back, scrub tap → ${s.t}/${s.dur.toFixed(1)} s, switch ${a0}→${a1}→back, no horizontal overflow`;
  }, "5 review page lists the clip, opens the editor");

  // --- cleanup
  if (!KEEP) for (const id of jobs) { const r = await api(ctxMain, "DELETE", `/api/jobs/${id}`); notes.push(`cleanup job ${id.slice(0, 8)}: DELETE ${r.s}`); }
  if (errs.length) notes.push(`page errors: ${[...new Set(errs)].slice(0, 4).join(" | ")}`);
  for (const [label, c] of ctxs) { await c.tracing.stop({ path: path.join(OUT, `trace-${label}.zip`) }).catch(() => {}); await c.close().catch(() => {}); }
  await browser.close();

  // --- report
  const slow = [];
  if (times.analyze_s > 600) slow.push(`analysis took ${(times.analyze_s / 60).toFixed(1)} min for a 4 m 44 s video (> 10 min)`);
  const tm = (notes.find((n) => n.startsWith("stage timings")) || "").match(/(\w+) (\d+(?:\.\d+)?)s/g) || []; const parsed = tm.map((x) => x.split(" ")).filter((x) => x[0] !== "total").map((x) => [x[0], parseFloat(x[1])]).sort((a, b) => b[1] - a[1]);
  if (parsed[0] && parsed[0][1] > 120) slow.push(`slowest analysis stage: ${parsed[0][0]} ${parsed[0][1].toFixed(0)} s${parsed[1] ? `, then ${parsed[1][0]} ${parsed[1][1].toFixed(0)} s` : ""}`);
  if (times.preview_s > 60) slow.push(`preview render ${times.preview_s.toFixed(0)} s (> 60 s)`);
  if (times.final_s > 120) slow.push(`final render ${times.final_s.toFixed(0)} s (> 120 s)`);
  for (const s of steps) if (s.status === "FAIL") slow.push(`BROKEN: ${s.name}: ${s.note}`);
  const fails = steps.filter((s) => s.status === "FAIL").length;
  const rep = [`# Staging e2e — ${new Date().toISOString()}`, "", `Target ${BASE} · user ${USER} · video ${URL_} · ${fails ? "**FAIL**" : "PASS"} (${steps.filter((s) => s.status === "PASS").length} pass, ${fails} fail, ${steps.filter((s) => s.status === "SKIP").length} skipped)`, "",
    "| Step | Result | Time | Notes |", "|---|---|---|---|", ...steps.map((s) => `| ${s.name} | ${s.status} | ${s.secs ? s.secs.toFixed(1) + " s" : ""} | ${(s.note || "").replace(/\|/g, "/")} |`), "",
    "## Slow or broken", ...(slow.length ? slow.map((x) => `- ${x}`) : ["- nothing flagged"]), "", "## Stage times", ...Object.entries(times).map(([k, v]) => `- ${k.replace("_s", "")}: ${v.toFixed(0)} s`), "", "## Audio (ebur128)",
    ...(pr.A ? [`- baseline preview: ${fmt(pr.A)}`] : []), ...(pr.B ? [`- preview after audio edits (${pr.editWas}): ${fmt(pr.B)}`] : []), ...(pr.F ? [`- final: ${fmt(pr.F)}`] : []), "", "## Notes", ...notes.map((n) => `- ${n}`), "", `Artifacts: ${OUT} (video/, trace-*.zip, *.png)`];
  fs.writeFileSync(path.join(OUT, "report.md"), rep.join("\n")); if (process.env.E2E_REPORT_COPY) fs.writeFileSync(process.env.E2E_REPORT_COPY, rep.join("\n")); console.log("\n" + rep.join("\n")); process.exit(fails ? 1 : 0);
})().catch((e) => { console.error("e2e crashed:", e.message); process.exit(2); });
