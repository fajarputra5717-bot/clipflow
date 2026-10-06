/* Review page (lane B, P4 task 6 + Lane C carry-over) — flow-preview step 4 as its own view.
   Loaded by one <script> in index.html (<!-- lane-b hook -->), mounted into the app shell like the
   editor (toolbar, stepper, island stay). Route: #review or #review/<jobId>.
   Data: GET /api/jobs?scope=queue (picker), GET /api/jobs/{id} (candidates + rule_checks, the ONE
   source for chips and the approve gate, shared/rule_checks.py). Quick fixes: length → PUT
   …/editor/fix-length (editor cuts), hashtags/dismiss → POST …/fix-rule, watermark → regenerate-preview.
   Progress = the island (/api/activity); cards are keyed and patched in place while renders run. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const RUNNING = ["preview_queued", "preview_rendering", "render_queued", "rendering", "thumbnail_queued", "thumbnail_rendering"];
  const READY = ["review", "completed", "partial_failure"];
  const R = { jid: null, jobs: [], job: null, hidden: [], pollT: 0, open: false, sig: {} };
  const enc = encodeURIComponent;

  function section() {
    let s = $("reviewSection");
    if (s) return s;
    const anchor = $("currentSection");
    if (!anchor) return null;
    s = document.createElement("section");
    s.id = "reviewSection"; s.className = "view-section rv-page"; s.hidden = true; s.setAttribute("aria-label", "Review");
    anchor.parentElement.appendChild(s);
    return s;
  }

  // ------------------------------------------------------------------ routing
  function route() {
    const m = location.hash.match(/^#review(?:\/([^/?#]+))?$/);
    if (m) show(m[1] ? decodeURIComponent(m[1]) : null);
    else if (R.open) hide();
  }

  async function show(jid) {
    const s = section(); if (!s) return;
    // Put the shell (toolbar title + stepper, Lane A's showTab) on its Review step first, then take over
    // that step's content area: the stepper highlights Review exactly like the mockup's step 4.
    if (!R.open && typeof window.showTab === "function") {
      try { await window.showTab("queue"); } catch (_) { /* shell keeps working without it */ }
    }
    if (!R.open) {
      R.hidden = [...s.parentElement.querySelectorAll(":scope > .view-section")].filter((v) => v !== s && !v.hidden)
        .map((v) => [v, v.classList.contains("hidden")]);
      R.hidden.forEach(([v]) => v.classList.add("hidden"));
      s.hidden = false; s.classList.remove("hidden"); R.open = true;
      s.innerHTML = `<div class="rv-picker" id="rvPicker"></div><div id="rvBody"><div class="panel rv-loading">Loading clips…</div></div>`;
    }
    const t = $("pageTitle"); if (t) t.textContent = "Review";
    try {
      R.jobs = (await api("/api/jobs?scope=queue")).filter((j) => READY.includes(j.status) || RUNNING.includes(j.status));
    } catch (e) { $("rvBody").innerHTML = `<div class="panel error-box">Can't load jobs: ${esc(e.message)}</div>`; return; }
    if (!R.jobs.length) { $("rvPicker").innerHTML = ""; $("rvBody").innerHTML = `<div class="panel rv-empty">No clips to review yet. Analyze a video first.</div>`; return; }
    R.jid = jid && R.jobs.some((j) => String(j.id) === String(jid)) ? jid : R.jobs[0].id;
    paintPicker();
    await loadJob();
  }

  function hide() {
    clearInterval(R.pollT);
    const s = $("reviewSection");
    if (s) { s.hidden = true; s.classList.add("hidden"); s.innerHTML = ""; }
    R.hidden.forEach(([v, had]) => v.classList.toggle("hidden", had));
    R.hidden = []; R.open = false; R.job = null; R.sig = {};
    if (typeof window.syncPageTitle === "function") window.syncPageTitle();
  }

  // ------------------------------------------------------------------ helpers
  const jobTitle = (j) => j.custom_title || j.source_title || "Untitled video";
  const campaignName = (slug) => (typeof window.campaignName === "function" ? window.campaignName(slug) : slug);
  const day = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); } catch (_) { return ""; } };
  const badge = (status) => (typeof window.badgeClass === "function" ? window.badgeClass(status) : "");
  const label = (status) => (typeof window.stageLabel === "function" ? window.stageLabel(status) : status);
  const fmtLen = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

  function outputSeconds(c) {                         // same rule as shared/rule_checks._duration
    const clip = Math.max(0, (c.end_time || 0) - (c.start_time || 0));
    const cuts = c.edit_spec && c.edit_spec.cuts;
    if (!cuts || !clip) return clip;
    const [a, b0] = cuts.trim || [0, clip], b = Math.min(b0, clip);
    const removed = (cuts.removed || []).reduce((t, [s, e]) => t + Math.max(0, Math.min(e, b) - Math.max(s, a)), 0);
    return Math.max(0, b - a - removed);
  }

  function reasonHtml(text) {                         // key phrase (first clause) bold, like the mockup
    const t = (text || "").trim();
    if (!t) return "";
    const m = t.match(/^(.{12,90}?)(?:[.;:—–]\s|,\s)/);
    return m ? `<b>${esc(m[1])}</b>${esc(t.slice(m[1].length))}` : esc(t);
  }

  const sorted = (cands) => cands.slice().sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || (a.clip_index ?? 0) - (b.clip_index ?? 0));

  // ------------------------------------------------------------------ picker
  function paintPicker(openList) {
    const cur = R.jobs.find((j) => String(j.id) === String(R.jid));
    const row = (j) => `
      <span class="rv-pick-main"><span class="rv-pick-title">${esc(jobTitle(j))}</span>
        <span class="rv-pick-sub">YouTube · ${esc(j.campaign ? campaignName(j.campaign) : "No campaign")} · ${esc(day(j.created_at))}</span></span>
      <span class="badge ${badge(j.status)}">${esc(label(j.status))}</span>`;
    $("rvPicker").innerHTML = `
      <button type="button" class="rv-pick" data-rv-pick aria-haspopup="listbox" aria-expanded="${!!openList}" aria-label="Choose a job">${row(cur)}<span class="rv-chev" aria-hidden="true">▾</span></button>
      <div class="rv-list" role="listbox" aria-label="Jobs" ${openList ? "" : "hidden"}>
        ${R.jobs.map((j) => `<button type="button" role="option" class="rv-opt" data-rv-job="${esc(j.id)}" aria-selected="${String(j.id) === String(R.jid)}">${row(j)}</button>`).join("")}
      </div>`;
  }

  // ------------------------------------------------------------------ job + cards
  async function loadJob() {
    clearInterval(R.pollT); R.sig = {};
    let j;
    try { j = await api(`/api/jobs/${enc(R.jid)}`); } catch (e) { $("rvBody").innerHTML = `<div class="panel error-box">Can't load this job: ${esc(e.message)}</div>`; return; }
    R.job = j;
    const cands = sorted(j.candidates || []);
    $("rvBody").innerHTML = `
      <section class="panel rv-panel">
        <div class="rv-head">
          <div><div class="rv-eyebrow">Step 4 · Review</div>
            <h2 class="rv-title">${esc(jobTitle(j))}</h2>
            <p class="rv-desc">Clips are sorted by hook score. A clip can be scheduled only when every campaign rule passes.</p></div>
          <span class="badge attention rv-count" id="rvCount"></span>
        </div>
        <div class="rv-grid" id="rvGrid">${cands.map((c) => `<article class="rv-clip" id="rv-${esc(c.id)}" data-rv-card="${esc(c.id)}"></article>`).join("")}</div>
        ${cands.length ? "" : `<p class="rv-empty">This job has no clips.</p>`}
      </section>`;
    patch(j);
    R.pollT = setInterval(poll, window.POLL_INTERVAL || 2200);
  }

  async function poll() {
    if (!R.open || !R.jid) return;
    if (!(R.job.candidates || []).some((c) => RUNNING.includes(c.status)) && !R.dirty) return;
    try { const j = await api(`/api/jobs/${enc(R.jid)}`); R.dirty = false; R.job = j; patch(j); } catch (_) { /* keep last state */ }
  }

  function patch(j) {
    const cands = j.candidates || [];
    const toReview = cands.filter((c) => c.status === "review").length;
    const cnt = $("rvCount"); if (cnt) { cnt.textContent = `${toReview} to review`; cnt.hidden = !toReview; }
    cands.forEach((c) => {
      const el = $("rv-" + c.id); if (!el) return;
      const sig = JSON.stringify([c.status, c.score, c.title, c.manual_title, c.ai_title, c.reason, c.rule_checks, c.edit_spec && c.edit_spec.cuts, c.updated_at]);
      if (R.sig[c.id] === sig) return;                     // keyed: only cards that changed are repainted
      R.sig[c.id] = sig;
      el.innerHTML = card(j, c);
      el.classList.toggle("approved", ["render_queued", "rendering", "completed"].includes(c.status));
    });
  }

  function chipHtml(jid, c, ch) {
    if (ch.ok) return `<span class="badge completed" title="${esc(ch.detail || "")}">✓ ${esc(ch.label)}</span>`;
    const cls = ch.blocking ? "failed" : "attention";
    const fixes = { trim: ch.fix_target ? `Trim to ${ch.fix_target} s` : null, hashtags: "Add tags", rerender: "Fix watermark", dismiss: "Dismiss" };
    const fixLabel = ch.fix && fixes[ch.fix];
    const busy = RUNNING.includes(c.status);
    return `<span class="rv-check"><span class="badge ${cls}" title="${esc(ch.detail || "")}">${ch.blocking ? "✗" : "!"} ${esc(ch.label)}</span>${fixLabel
      ? `<button type="button" class="rv-fix" data-rv-fix="${esc(ch.fix)}" data-rv-cid="${esc(c.id)}" data-rv-target="${ch.fix_target || ""}" ${busy ? "disabled" : ""}>${esc(fixLabel)}</button>` : ""}</span>`;
  }

  function card(j, c) {
    const jid = j.id, title = c.manual_title || c.title || c.ai_title || "Untitled clip";
    const chips = c.rule_checks || [];
    const blocking = chips.filter((ch) => ch.blocking && !ch.ok).length;
    const out = outputSeconds(c);
    const thumb = typeof window.mediaUrl === "function" ? mediaUrl(`/api/jobs/${jid}/candidates/${c.id}/thumbnail?v=${enc(c.updated_at || "")}`) : "";
    const state = c.status === "review" ? "" : `<span class="badge ${badge(c.status)}">${esc(label(c.status))}</span>`;
    const canApprove = c.status === "review" && !blocking;
    const hint = c.status !== "review" ? (c.status === "completed" ? "Final rendered." : RUNNING.includes(c.status) ? "Rendering… (progress in the island)" : "")
      : chips.length ? (blocking ? `Fix ${blocking} rule${blocking === 1 ? "" : "s"} to approve.` : "All campaign rules pass.") : "No campaign rules for this job.";
    return `
      <div class="rv-frame">${thumb ? `<img src="${thumb}" alt="" loading="lazy" onerror="this.remove()">` : ""}
        <span class="rv-time">${fmtLen(out)}</span></div>
      <div class="rv-info">
        <div class="rv-row">${c.score != null ? `<span class="rv-score" title="AI estimate of the hook strength">Hook ${Math.round(c.score)}</span><span class="rv-est">AI estimate</span>` : ""}<span class="rv-spacer"></span>${state}</div>
        <h3 class="rv-ctitle">${esc(title)}</h3>
        ${c.reason ? `<p class="rv-reason">${reasonHtml(c.reason)}</p>` : ""}
        ${chips.length ? `<div class="rv-checks">${chips.map((ch) => chipHtml(jid, c, ch)).join("")}</div>` : ""}
        <div class="rv-actions">
          <button type="button" class="primary" data-rv-approve="${esc(c.id)}" ${canApprove ? "" : "disabled"}>Approve</button>
          <a class="secondary btn-link rv-open" href="#editor/${esc(jid)}/${esc(c.id)}">Open editor</a>
        </div>
        <p class="rv-hint">${esc(hint)}</p>
      </div>`;
  }

  // ------------------------------------------------------------------ actions
  async function fix(btn) {
    const cid = btn.dataset.rvCid, kind = btn.dataset.rvFix, base = `/api/jobs/${enc(R.jid)}/candidates/${enc(cid)}`;
    setBusy(btn, true);
    try {
      if (kind === "trim") await api(`${base}/editor/fix-length`, { method: "PUT", body: JSON.stringify({ target: Number(btn.dataset.rvTarget) }) });
      else if (kind === "rerender") await api(`${base}/regenerate-preview`, { method: "POST" });
      else await api(`${base}/fix-rule`, { method: "POST", body: JSON.stringify({ rule: kind }) });
      R.job = await api(`/api/jobs/${enc(R.jid)}`); patch(R.job);
    } catch (e) { setBusy(btn, false); alert("Fix failed: " + e.message); }
  }

  async function approve(btn) {
    const cid = btn.dataset.rvApprove;
    setBusy(btn, true, "Approving…");
    try {
      await api(`/api/jobs/${enc(R.jid)}/candidates/${enc(cid)}/approve`, { method: "POST" });
      R.job = await api(`/api/jobs/${enc(R.jid)}`); patch(R.job);
    } catch (e) { setBusy(btn, false); alert("Approve failed: " + e.message); }
  }

  document.addEventListener("click", (e) => {
    if (R.open && e.target.closest("[data-nav],[data-flow-editor]")) { hide(); return; }
    const t = e.target.closest("[data-rv-pick],[data-rv-job],[data-rv-fix],[data-rv-approve]");
    if (!t) { if (R.open && !e.target.closest(".rv-list")) { const l = document.querySelector(".rv-list"); if (l && !l.hidden) paintPicker(false); } return; }
    if (t.matches("[data-rv-pick]")) { paintPicker(t.getAttribute("aria-expanded") !== "true"); return; }
    if (t.matches("[data-rv-job]")) { history.replaceState(null, "", `#review/${enc(t.dataset.rvJob)}`); R.jid = t.dataset.rvJob; paintPicker(false); loadJob(); return; }
    if (t.matches("[data-rv-fix]")) return fix(t);
    if (t.matches("[data-rv-approve]")) return approve(t);
  }, true);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && R.open) { const l = document.querySelector(".rv-list"); if (l && !l.hidden) { paintPicker(false); document.querySelector("[data-rv-pick]")?.focus(); } }
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("load", () => setTimeout(route, 0));
  window.clipflowReview = { open: (jid) => { location.hash = jid ? `#review/${jid}` : "#review"; } };
})();
