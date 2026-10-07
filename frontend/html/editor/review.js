/* Review page (lane B, P4 task 6 + filters) — flow-preview step 4 as its own view, mock card design kept.
   Loaded by one <script> in index.html (<!-- lane-b hook -->), mounted in the app shell on its Review step.
   Route: #review (filters) or #review/<jobId> (job filter preset, e.g. from the editor's "← Review").
   Filter bar: Campaign (All / each / No campaign) · Job (All jobs / one) · Status (To review / Approved / All),
   remembered per user (GET/PUT /api/review/filter → user_settings). Clips: GET /api/review/clips (owner-scoped,
   rule_checks = the ONE source for chips + the approve gate, earn state from payouts.py: "Week closed" /
   "Campaign ended" clips sorted last). Fixes: length → PUT …/editor/fix-length, hashtags/dismiss → POST
   …/fix-rule, watermark → regenerate-preview. Progress = the island; cards are keyed + patched in place. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const enc = encodeURIComponent;
  const RUNNING = ["preview_queued", "preview_rendering", "render_queued", "rendering", "thumbnail_queued", "thumbnail_rendering"];
  const STATUS = [["to_review", "To review"], ["approved", "Approved"], ["all", "All"]];
  const R = { open: false, hidden: [], filter: { campaign: "all", job: "all", status: "to_review" }, jobs: [], campaigns: [],
              data: null, sig: {}, pollT: 0, saveT: 0, loadSeq: 0 };

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

  async function show(jobFromHash) {
    const s = section(); if (!s) return;
    if (!R.open) {
      // shell on its Review step first (Lane A's showTab): title + stepper read "Review" like the mockup
      if (typeof window.showTab === "function") { try { await window.showTab("queue"); } catch (_) { /* keep going */ } }
      R.hidden = [...s.parentElement.querySelectorAll(":scope > .view-section")].filter((v) => v !== s && !v.hidden)
        .map((v) => [v, v.classList.contains("hidden")]);
      R.hidden.forEach(([v]) => v.classList.add("hidden"));
      s.hidden = false; s.classList.remove("hidden"); R.open = true;
      s.innerHTML = `<div class="rv-filters" id="rvFilters" role="group" aria-label="Filter clips"></div>
        <div id="rvBody"><div class="panel rv-loading">Loading clips…</div></div>`;
      try {
        const [f, jobs, camps] = await Promise.all([api("/api/review/filter"), api("/api/jobs?scope=queue"), api("/api/campaigns").catch(() => [])]);
        R.filter = f; R.jobs = jobs; R.campaigns = Array.isArray(camps) ? camps : [];
      } catch (e) { $("rvBody").innerHTML = `<div class="panel error-box">Can't load the review list: ${esc(e.message)}</div>`; return; }
    }
    const t = $("pageTitle"); if (t) t.textContent = "Review";
    if (jobFromHash) {
      const j = R.jobs.find((x) => String(x.id) === String(jobFromHash));
      R.filter = { ...R.filter, job: String(jobFromHash), campaign: j ? (j.campaign || "none") : R.filter.campaign };
    }
    paintFilters();
    await load();
  }

  function hide() {
    clearInterval(R.pollT);
    const s = $("reviewSection");
    if (s) { s.hidden = true; s.classList.add("hidden"); s.innerHTML = ""; }
    R.hidden.forEach(([v, had]) => v.classList.toggle("hidden", had));
    R.hidden = []; R.open = false; R.data = null; R.sig = {};
    if (typeof window.syncPageTitle === "function") window.syncPageTitle();
  }

  // ------------------------------------------------------------------ helpers
  const jobTitle = (j) => j.custom_title || j.source_title || "Untitled video";
  const campName = (slug) => (R.campaigns.find((c) => c.slug === slug) || {}).name || slug;
  const shortName = (name) => String(name || "").split(/\s+X\s+/i)[0];
  const day = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }); } catch (_) { return ""; } };
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

  // ------------------------------------------------------------------ filters
  function jobsForCampaign() {
    const c = R.filter.campaign;
    return R.jobs.filter((j) => c === "all" || (c === "none" ? !j.campaign : j.campaign === c));
  }
  function paintFilters() {
    const f = R.filter, used = [...new Set(R.jobs.map((j) => j.campaign).filter(Boolean))];
    const camps = [...new Set([...R.campaigns.map((c) => c.slug), ...used])];
    const jobs = jobsForCampaign();
    if (f.job !== "all" && !jobs.some((j) => String(j.id) === f.job)) f.job = "all";
    $("rvFilters").innerHTML = `
      <label class="rv-f"><span>Campaign</span>
        <select data-rv-filter="campaign">
          <option value="all" ${f.campaign === "all" ? "selected" : ""}>All campaigns</option>
          ${camps.map((s) => `<option value="${esc(s)}" ${f.campaign === s ? "selected" : ""}>${esc(campName(s))}</option>`).join("")}
          <option value="none" ${f.campaign === "none" ? "selected" : ""}>No campaign</option>
        </select></label>
      <label class="rv-f rv-f-job"><span>Job</span>
        <select data-rv-filter="job">
          <option value="all">All jobs${jobs.length ? ` (${jobs.length})` : ""}</option>
          ${jobs.map((j) => `<option value="${esc(j.id)}" ${String(j.id) === f.job ? "selected" : ""}>${esc(jobTitle(j))} · ${esc(day(j.created_at))}</option>`).join("")}
        </select></label>
      <div class="rv-f"><span id="rvStatusLbl">Status</span>
        <div class="rv-seg" role="group" aria-labelledby="rvStatusLbl">
          ${STATUS.map(([v, n]) => `<button type="button" data-rv-status="${v}" aria-pressed="${f.status === v}">${n}</button>`).join("")}
        </div></div>`;
  }
  function setFilter(patch) {
    R.filter = { ...R.filter, ...patch };
    if ("campaign" in patch) R.filter.job = "all";
    history.replaceState(null, "", R.filter.job !== "all" ? `#review/${enc(R.filter.job)}` : "#review");
    paintFilters();
    clearTimeout(R.saveT);
    R.saveT = setTimeout(() => api("/api/review/filter", { method: "PUT", body: JSON.stringify(R.filter) }).catch(() => {}), 400);
    load();
  }

  // ------------------------------------------------------------------ clips
  const clipsUrl = () => `/api/review/clips?campaign=${enc(R.filter.campaign)}&job=${enc(R.filter.job)}&status=${enc(R.filter.status)}`;

  async function load() {
    clearInterval(R.pollT); R.sig = {};
    const seq = ++R.loadSeq;
    let d;
    try { d = await api(clipsUrl()); }
    catch (e) { if (seq === R.loadSeq) $("rvBody").innerHTML = `<div class="panel error-box">Can't load clips: ${esc(e.message)}</div>`; return; }
    if (seq !== R.loadSeq || !R.open) return;                  // a newer filter won
    R.data = d;
    const h = d.header;
    const statusLine = h.kind === "campaign" && h.status ? `<p class="rv-camp-status">${esc(shortName(h.title))} · ${esc(h.status.text)}</p>` : "";
    $("rvBody").innerHTML = `
      <section class="panel rv-panel">
        <div class="rv-head">
          <div><div class="rv-eyebrow">Step 4 · Review</div>
            <h2 class="rv-title">${esc(h.title || (h.kind === "job" ? "Untitled video" : "Clips"))}</h2>
            ${statusLine}
            <p class="rv-desc">Clips are sorted by hook score. A clip can be scheduled only when every campaign rule passes.</p></div>
          <span class="badge attention rv-count" id="rvCount"></span>
        </div>
        ${d.clips.length ? `<div class="rv-grid" id="rvGrid">${d.clips.map((c) => `<article class="rv-clip" id="rv-${esc(c.id)}"></article>`).join("")}</div>`
                         : emptyState()}
      </section>`;
    patch(d);
    R.pollT = setInterval(poll, window.POLL_INTERVAL || 2200);
  }

  function emptyState() {
    const f = R.filter, name = f.campaign === "all" ? "" : f.campaign === "none" ? "no-campaign " : shortName(campName(f.campaign)) + " ";
    const what = f.status === "approved" ? `No approved ${name}clips yet.` : f.status === "all" ? `No ${name}clips yet.` : `No ${name}clips to review.`;
    return `<div class="rv-empty-state"><p class="rv-empty-title">${esc(what)}</p>
      <p class="rv-desc">Import a video on <a href="#" data-rv-analyze>Analyze</a>${f.status !== "all" ? ", or switch the status filter to All." : "."}</p></div>`;
  }

  async function poll() {
    if (!R.open || !R.data || !R.data.clips.some((c) => RUNNING.includes(c.status))) return;
    try { await refresh(); } catch (_) { /* keep last state */ }
  }
  async function refresh() {
    const d = await api(clipsUrl());
    if (!R.data || d.clips.map((c) => c.id).join() !== R.data.clips.map((c) => c.id).join()) return load();   // set changed
    R.data = d; patch(d);
  }

  function patch(d) {
    const cnt = $("rvCount"); if (cnt) { cnt.textContent = `${d.header.to_review} to review`; cnt.hidden = !d.header.to_review; }
    d.clips.forEach((c) => {
      const el = $("rv-" + c.id); if (!el) return;
      const sig = JSON.stringify(c);
      if (R.sig[c.id] === sig) return;                   // keyed: only changed cards repaint
      R.sig[c.id] = sig;
      el.innerHTML = card(c);
      el.classList.toggle("approved", ["render_queued", "rendering", "completed"].includes(c.status));
      el.classList.toggle("no-earn", !!c.earn);
    });
  }

  function chipHtml(c, ch) {
    if (ch.ok) return `<span class="badge completed" title="${esc(ch.detail || "")}">✓ ${esc(ch.label)}</span>`;
    const fixes = { trim: ch.fix_target ? `Trim to ${ch.fix_target} s` : null, hashtags: "Add tags", rerender: "Fix watermark", dismiss: "Dismiss" };
    const fixLabel = ch.fix && fixes[ch.fix];
    return `<span class="rv-check"><span class="badge ${ch.blocking ? "failed" : "attention"}" title="${esc(ch.detail || "")}">${ch.blocking ? "✗" : "!"} ${esc(ch.label)}</span>${fixLabel
      ? `<button type="button" class="rv-fix" data-rv-fix="${esc(ch.fix)}" data-rv-cid="${esc(c.id)}" data-rv-jid="${esc(c.job_id)}" data-rv-target="${ch.fix_target || ""}" ${RUNNING.includes(c.status) ? "disabled" : ""}>${esc(fixLabel)}</button>` : ""}</span>`;
  }

  function card(c) {
    const title = c.manual_title || c.title || c.ai_title || "Untitled clip";
    const chips = c.rule_checks || [];
    const blocking = chips.filter((ch) => ch.blocking && !ch.ok).length;
    const thumb = typeof window.mediaUrl === "function" ? mediaUrl(`/api/jobs/${c.job_id}/candidates/${c.id}/thumbnail?v=${enc(c.updated_at || "")}`) : "";
    const state = c.status === "review" ? "" : `<span class="badge ${badge(c.status)}">${esc(label(c.status))}</span>`;
    const earn = c.earn ? `<span class="badge cancelled rv-earn" title="This clip can no longer earn">${esc(c.earn.label)}</span>` : "";
    const canApprove = c.status === "review" && !blocking;
    const hint = c.status !== "review" ? (c.status === "completed" ? "Final rendered." : RUNNING.includes(c.status) ? "Rendering… (progress in the island)" : "")
      : chips.length ? (blocking ? `Fix ${blocking} rule${blocking === 1 ? "" : "s"} to approve.` : "All campaign rules pass.") : "No campaign rules for this job.";
    const src = R.filter.job === "all" ? `<div class="rv-src">${esc(c.job_title)} · ${esc(day(c.job_date))}</div>` : "";
    return `
      <div class="rv-frame">${thumb ? `<img src="${thumb}" alt="" loading="lazy" onerror="this.remove()">` : ""}
        <span class="rv-time">${fmtLen(outputSeconds(c))}</span></div>
      <div class="rv-info">
        ${src}
        <div class="rv-row">${c.score != null ? `<span class="rv-score" title="AI estimate of the hook strength">Hook ${Math.round(c.score)}</span><span class="rv-est">AI estimate</span>` : ""}<span class="rv-spacer"></span>${earn}${state}</div>
        <h3 class="rv-ctitle">${esc(title)}</h3>
        ${c.reason ? `<p class="rv-reason">${reasonHtml(c.reason)}</p>` : ""}
        ${chips.length ? `<div class="rv-checks">${chips.map((ch) => chipHtml(c, ch)).join("")}</div>` : ""}
        <div class="rv-actions">
          <button type="button" class="primary" data-rv-approve="${esc(c.id)}" data-rv-jid="${esc(c.job_id)}" ${canApprove ? "" : "disabled"}>Approve</button>
          <a class="secondary btn-link rv-open" href="#editor/${esc(c.job_id)}/${esc(c.id)}">Open editor</a>
        </div>
        <p class="rv-hint">${esc(hint)}</p>
      </div>`;
  }

  // ------------------------------------------------------------------ actions
  async function fix(btn) {
    const base = `/api/jobs/${enc(btn.dataset.rvJid)}/candidates/${enc(btn.dataset.rvCid)}`, kind = btn.dataset.rvFix;
    setBusy(btn, true);
    try {
      if (kind === "trim") await api(`${base}/editor/fix-length`, { method: "PUT", body: JSON.stringify({ target: Number(btn.dataset.rvTarget) }) });
      else if (kind === "rerender") await api(`${base}/regenerate-preview`, { method: "POST" });
      else await api(`${base}/fix-rule`, { method: "POST", body: JSON.stringify({ rule: kind }) });
      await refresh();
    } catch (e) { alert("Fix failed: " + e.message); }
    finally { if (btn.isConnected) setBusy(btn, false); }       // QA Low 3: never rely on the re-render
  }
  async function approve(btn) {
    setBusy(btn, true, "Approving…");
    try {
      await api(`/api/jobs/${enc(btn.dataset.rvJid)}/candidates/${enc(btn.dataset.rvApprove)}/approve`, { method: "POST" });
      await refresh();
    } catch (e) { alert("Approve failed: " + e.message); }
    finally { if (btn.isConnected) setBusy(btn, false); }
  }

  document.addEventListener("click", (e) => {
    if (R.open && e.target.closest("[data-nav],[data-flow-editor]")) { hide(); return; }
    const t = e.target.closest("[data-rv-status],[data-rv-fix],[data-rv-approve],[data-rv-analyze]");
    if (!t || !R.open) return;
    if (t.matches("[data-rv-status]")) return setFilter({ status: t.dataset.rvStatus });
    if (t.matches("[data-rv-fix]")) return fix(t);
    if (t.matches("[data-rv-approve]")) return approve(t);
    if (t.matches("[data-rv-analyze]")) { e.preventDefault(); hide(); history.replaceState(null, "", location.pathname); document.querySelector('[data-nav="current"]')?.click(); }
  }, true);
  document.addEventListener("change", (e) => {
    const sel = e.target.closest("[data-rv-filter]");
    if (sel && R.open) setFilter({ [sel.dataset.rvFilter]: sel.value });
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("load", () => setTimeout(route, 0));
  window.clipflowReview = { open: (jid) => { location.hash = jid ? `#review/${jid}` : "#review"; } };
})();
