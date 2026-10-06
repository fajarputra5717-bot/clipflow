/* Editor page (lane B, roadmap P4) — flow-preview step 5 as its own view, not a drawer.
   Loaded by one <script> in index.html (<!-- lane-b hook -->) and mounted into the app shell, so the
   toolbar, stepper and Dynamic Island stay. Route: #editor/<jobId>/<candidateId> ("Open editor").
   Uses index.html's helpers: api() (auth), mediaUrl() (media token), setBusy(), esc().
   Progress for renders is the island (/api/activity, CLAUDE.md 090): no spinners or bars here.
   Task 1: hook title card (toggle, text, 2/2.5/3 s), live preview overlay + Render preview. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const RENDERING = ["preview_queued", "preview_rendering", "render_queued", "rendering"];
  const TABS = [["captions", "Captions"], ["effects", "Effects"], ["audio", "Audio"], ["watermark", "Watermark"], ["export", "Export"]];
  const READY_TABS = new Set(["captions"]);   // the rest arrive with P4 tasks 3–5
  const edUrl = (jid, cid) => `/api/jobs/${encodeURIComponent(jid)}/candidates/${encodeURIComponent(cid)}/editor`;
  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PPS = 100;                              // timeline pixels per second
  const E = { tl: null, raf: 0, nowWord: -1, jid: null, cid: null, state: null, hook: null, saveT: 0, pollT: 0, hidden: [], tab: "captions", busy: false };

  function section() {
    let s = $("editorSection");
    if (s) return s;
    const anchor = $("currentSection");
    if (!anchor) return null;
    s = document.createElement("section");
    s.id = "editorSection";
    s.className = "view-section ed-page";
    s.hidden = true;
    s.setAttribute("aria-label", "Editor");
    anchor.parentElement.appendChild(s);
    return s;
  }

  // ------------------------------------------------------------------ routing
  function route() {
    const m = location.hash.match(/^#editor\/([^/]+)\/([^/?#]+)/);
    if (m) open(decodeURIComponent(m[1]), decodeURIComponent(m[2]));
    else if (E.cid) close(false);
  }

  async function open(jid, cid) {
    const s = section();
    if (!s) return;
    if (!E.cid) {                         // remember which views were showing, to restore on close
      E.hidden = [...s.parentElement.querySelectorAll(":scope > .view-section")]
        .filter((v) => v !== s).map((v) => [v, v.classList.contains("hidden"), v.hidden]);
      E.hidden.forEach(([v]) => { v.classList.add("hidden"); });
    }
    E.jid = jid; E.cid = cid; E.tab = "captions";
    s.hidden = false; s.classList.remove("hidden");
    document.body.classList.add("editor-open");
    const t = $("pageTitle"); if (t) t.textContent = "Editor";
    window.scrollTo({ top: 0, behavior: "auto" });
    s.innerHTML = `<div class="panel ed-loading" aria-busy="true">Loading the editor…</div>`;
    try {
      E.state = await api(edUrl(jid, cid));
      E.hook = { ...E.state.hook_title };
      render();
      if (RENDERING.includes(E.state.candidate.status)) watchRender();
    } catch (e) {
      s.innerHTML = `<div class="panel error-box">Can't open this clip: ${esc(e.message)} <a href="#" data-ed-back>Back</a></div>`;
    }
  }

  function close(setHash = true) {
    clearTimeout(E.saveT); clearInterval(E.pollT); cancelAnimationFrame(E.raf); E.tl = null; E.nowWord = -1;
    const s = $("editorSection");
    if (s) { s.hidden = true; s.classList.add("hidden"); s.innerHTML = ""; }
    E.hidden.forEach(([v, hadHidden]) => v.classList.toggle("hidden", hadHidden));
    E.hidden = []; E.cid = E.jid = null; E.state = null;
    document.body.classList.remove("editor-open");
    if (typeof window.syncPageTitle === "function") window.syncPageTitle();
    if (setHash && location.hash.startsWith("#editor/")) history.replaceState(null, "", location.pathname + location.search);
  }

  // ------------------------------------------------------------------ render
  function previewSrc() {
    const c = E.state.candidate;
    if (!c.has_preview) return "";
    return mediaUrl(`${c.preview_url}?v=${encodeURIComponent(c.updated_at || "")}`);
  }

  function render() {
    const s = $("editorSection"), st = E.state, c = st.candidate;
    s.innerHTML = `
      <div class="ed-head">
        <a class="ed-back" href="#" data-ed-back>← Review</a>
        <div class="ed-eyebrow">Editor${st.job.title ? " · " + esc(st.job.title) : ""}</div>
        <h2 class="ed-title">${esc(c.title || "Untitled clip")}</h2>
        ${c.reason ? `<p class="ed-reason">${esc(c.reason)}</p>` : ""}
      </div>
      <div class="ed-grid">
        <div class="ed-player">
          <div class="ed-frame" id="edFrame">
            ${c.has_preview ? `<video id="edVideo" src="${previewSrc()}" playsinline loop muted preload="metadata"></video>`
                            : `<div class="ed-novideo">No preview yet</div>`}
            <div class="ed-hook" id="edHook" aria-hidden="true"><span></span></div>
          </div>
          <div class="ed-pctrl">
            <button class="icon-btn" type="button" data-ed-play aria-label="Play" ${c.has_preview ? "" : "disabled"}>▶</button>
            <span class="ed-time" id="edTime">0:00</span>
            <span class="ed-note" id="edNote"></span>
          </div>
        </div>
        <div class="ed-insp">
          <div class="ed-seg" role="tablist" aria-label="Editor tools">
            <span class="ed-seg-ind" aria-hidden="true"></span>
            ${TABS.map(([id, n]) => `<button type="button" role="tab" id="edtab-${id}" aria-selected="${id === E.tab}"
               ${READY_TABS.has(id) ? "" : `aria-disabled="true" title="Coming in a later editor step"`}
               data-ed-tab="${id}">${n}</button>`).join("")}
          </div>
          <div class="ed-panel" role="tabpanel" aria-labelledby="edtab-captions">${captionsPanel()}</div>
        </div>
      </div>
      <div class="ed-tl" id="edTl" aria-label="Timeline"><div class="ed-hint">Loading the timeline…</div></div>
      <div class="ed-foot">
        <span class="ed-state" id="edState"></span>
        <span class="ed-spacer"></span>
        <button class="primary" type="button" data-ed-render>Render preview</button>
      </div>`;
    wirePlayer();
    paintHook();
    paintState();
    requestAnimationFrame(moveSeg);
    loadTimeline();
  }

  // ------------------------------------------------------------------ timeline (task 2)
  async function loadTimeline() {
    try {
      E.tl = await api(edUrl(E.jid, E.cid) + "/timeline");
      renderTimeline();
    } catch (e) {
      const el = $("edTl"); if (el) el.innerHTML = `<div class="ed-hint">Timeline unavailable: ${esc(e.message)}</div>`;
    }
  }

  function renderTimeline() {
    const el = $("edTl"), tl = E.tl;
    if (!el || !tl) return;
    const dur = Number(tl.duration) || 0, W = Math.max(1, Math.ceil(dur * PPS));
    let ruler = "";
    for (let t = 0; t <= dur; t++) ruler += `<i style="left:${t * PPS}px"></i>${t % 2 === 0 ? `<span style="left:${t * PPS}px">${fmt(t)}</span>` : ""}`;
    const chips = tl.words.map((w) => `<button type="button" class="ed-word" data-ed-word="${w.i}" title="${esc(w.text)} · ${w.start.toFixed(2)} s"
        style="left:${(w.start * PPS).toFixed(1)}px;width:${Math.max(16, (w.end - w.start) * PPS - 2).toFixed(1)}px">${esc(w.text)}</button>`).join("");
    el.innerHTML = `
      <div class="ed-tl-head"><span class="ed-label">Timeline</span>
        <span class="ed-hint">${E.state.candidate.has_preview ? "Click a word to jump there" : "Render a preview to play"}</span>
        <span class="ed-spacer"></span><span class="ed-time" id="edTlTime">0:00.0 / ${fmt(dur)}</span></div>
      <div class="ed-tl-scroll" id="edTlScroll">
        <div class="ed-tl-inner" id="edTlInner" style="width:${W}px" data-ed-seekarea>
          <div class="ed-tl-ruler" aria-hidden="true">${ruler}</div>
          <canvas class="ed-tl-wave" id="edWave" aria-hidden="true"></canvas>
          <div class="ed-tl-words" role="group" aria-label="Words">${chips}</div>
          <div class="ed-tl-playhead" id="edPlayhead" aria-hidden="true"></div>
        </div>
      </div>
      ${tl.peaks ? "" : `<div class="ed-hint">The waveform appears after the next Render preview.</div>`}`;
    drawWave();
    paintPlayhead();
  }

  function drawWave() {
    const cv = $("edWave"), tl = E.tl;
    if (!cv || !tl) return;
    const dpr = window.devicePixelRatio || 1, W = Math.ceil(tl.duration * PPS), H = 44;
    cv.style.width = W + "px"; cv.style.height = H + "px";
    cv.width = Math.ceil(W * dpr); cv.height = Math.ceil(H * dpr);
    const g = cv.getContext("2d");
    g.scale(dpr, dpr);
    g.fillStyle = getComputedStyle(cv).color || "#8e8e93";
    if (!tl.peaks) { g.fillRect(0, H / 2 - 0.5, W, 1); return; }
    const col = 3, per = tl.rate / PPS;              // peaks per pixel
    for (let x = 0; x < W; x += col) {
      let m = 0;
      for (let i = Math.floor(x * per); i < Math.min(tl.peaks.length, Math.floor((x + col) * per) + 1); i++) m = Math.max(m, tl.peaks[i]);
      const h = Math.max(1, m * (H - 4));
      g.fillRect(x, (H - h) / 2, col - 1, h);
    }
  }

  function wordAt(t) {                              // last word that started at or before t
    const w = E.tl ? E.tl.words : [];
    let lo = 0, hi = w.length - 1, ans = -1;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (w[mid].start <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
    return ans >= 0 && t < w[ans].end + 0.15 ? ans : -1;
  }

  function paintPlayhead(follow) {
    const v = $("edVideo"), ph = $("edPlayhead");
    if (!ph || !E.tl) return;
    const t = v ? v.currentTime : 0, x = t * PPS;
    ph.style.transform = `translateX(${x}px)`;
    const tm = $("edTlTime"); if (tm) tm.textContent = `${fmt(t)}.${Math.floor((t % 1) * 10)} / ${fmt(E.tl.duration)}`;
    const i = wordAt(t);
    if (i !== E.nowWord) {
      document.querySelector(".ed-word.now")?.classList.remove("now");
      if (i >= 0) document.querySelector(`[data-ed-word="${i}"]`)?.classList.add("now");
      E.nowWord = i;
    }
    const sc = $("edTlScroll");
    if (follow && sc && (x < sc.scrollLeft + 24 || x > sc.scrollLeft + sc.clientWidth - 48)) sc.scrollLeft = Math.max(0, x - 48);
  }

  function loop() {
    const v = $("edVideo");
    paintPlayhead(true);
    if (v && !v.paused && E.cid) E.raf = requestAnimationFrame(loop);
  }

  function seek(t) {
    const v = $("edVideo");
    if (!v || !E.state.candidate.has_preview) return;
    v.currentTime = Math.max(0, Math.min(t, (E.tl && E.tl.duration) || v.duration || t));
    paintPlayhead(false); paintHook();
  }

  function captionsPanel() {
    const h = E.hook;
    return `
      <div class="ed-group">
        <div class="ed-row">
          <div><div class="ed-label" id="edHookLbl">Hook title card</div>
            <div class="ed-hint">Big text over the first seconds, under the watermark. In the preview and the final.</div></div>
          <button class="ed-switch" type="button" role="switch" aria-checked="${h.on}" aria-labelledby="edHookLbl" data-ed-hook-on></button>
        </div>
        <div class="ed-dep ${h.on ? "" : "is-off"}" ${h.on ? "" : "inert"}>
          <label class="ed-field"><span>Text</span>
            <input type="text" id="edHookText" maxlength="${h.max_chars}" value="${esc(h.text)}"
                   placeholder="${esc(h.default_text || "Clip title")}" autocomplete="off">
          </label>
          <div class="ed-hint" id="edHookCount"></div>
          <div class="ed-row"><span class="ed-label">Show for</span>
            <div class="ed-chips" role="group" aria-label="Show the card for">
              ${h.durations.map((d) => `<button type="button" class="ed-chip" data-ed-hook-dur="${d}" aria-pressed="${Number(h.duration) === d}">${d} s</button>`).join("")}
            </div></div>
        </div>
      </div>`;
  }

  function hookText() { return (E.hook.text || E.hook.default_text || "").trim(); }

  function paintHook() {
    const el = $("edHook"), v = $("edVideo");
    if (!el) return;
    const t = v ? v.currentTime : 0;
    // The rendered preview already has the saved card baked in: the CSS overlay only stands in for
    // changes that aren't rendered yet (otherwise two cards would show).
    const show = !!E.dirty && E.hook.on && !!hookText() && t < Number(E.hook.duration);
    const note = $("edNote");
    if (note) note.textContent = E.dirty ? "The card on the video is a live preview: Render preview bakes it in." : "";
    el.querySelector("span").textContent = hookText();
    el.classList.toggle("show", show);
    const cnt = $("edHookCount");
    if (cnt) cnt.textContent = `${(E.hook.text || "").length}/${E.hook.max_chars}` + (E.hook.text ? "" : " · empty = the clip title");
  }

  function paintState(msg) {
    const el = $("edState"); if (!el) return;
    const c = E.state.candidate;
    if (msg) { el.textContent = msg; return; }
    if (RENDERING.includes(c.status)) el.textContent = "Rendering the preview…";
    else if (E.dirty) el.textContent = "Changes saved · not rendered yet";
    else el.textContent = c.has_preview ? "Preview is up to date" : "No preview yet";
  }

  function wirePlayer() {
    const v = $("edVideo"); if (!v) return;
    const tick = () => { paintHook(); const tm = $("edTime"); if (tm) tm.textContent = fmt(v.currentTime); };
    v.addEventListener("timeupdate", tick);
    v.addEventListener("seeked", () => { tick(); paintPlayhead(false); });
    v.addEventListener("play", () => { setPlay(true); cancelAnimationFrame(E.raf); E.raf = requestAnimationFrame(loop); });
    v.addEventListener("pause", () => setPlay(false));
    if (!reduced()) v.play().catch(() => {});
  }
  function setPlay(on) { const b = document.querySelector("[data-ed-play]"); if (b) { b.textContent = on ? "❚❚" : "▶"; b.setAttribute("aria-label", on ? "Pause" : "Play"); } }
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  function moveSeg() {
    const seg = document.querySelector(".ed-seg"); if (!seg) return;
    const b = seg.querySelector('[aria-selected="true"]'), ind = seg.querySelector(".ed-seg-ind");
    ind.style.width = b.offsetWidth + "px"; ind.style.transform = `translateX(${b.offsetLeft}px)`;
  }

  // ------------------------------------------------------------------ save + render
  function scheduleSave() {
    clearTimeout(E.saveT);
    paintState("Saving…");
    E.dirty = true; paintHook();
    E.saveT = setTimeout(save, 600);
  }
  async function save() {
    clearTimeout(E.saveT);
    const body = { on: E.hook.on, text: E.hook.text || "", duration: Number(E.hook.duration) };
    try {
      E.state = await api(edUrl(E.jid, E.cid) + "/hook-title", { method: "PUT", body: JSON.stringify(body) });
      E.dirty = true;
      paintState();
    } catch (e) { paintState("Not saved: " + e.message); throw e; }
  }

  async function renderPreview(btn) {
    if (E.busy) return;
    E.busy = true;
    setBusy(btn, true, "Rendering…");
    try {
      if (E.saveT) await save();
      await api(`/api/jobs/${encodeURIComponent(E.jid)}/candidates/${encodeURIComponent(E.cid)}/regenerate-preview`, { method: "POST" });
      E.state.candidate.status = "preview_queued";
      paintState();
      watchRender(btn);
    } catch (e) {
      setBusy(btn, false); E.busy = false;
      paintState("Render failed to start: " + e.message);
    }
  }

  function watchRender(btn) {
    btn = btn || document.querySelector("[data-ed-render]");
    if (btn && !btn.classList.contains("is-busy")) setBusy(btn, true, "Rendering…");
    E.busy = true;
    clearInterval(E.pollT);
    E.pollT = setInterval(async () => {
      try {
        const st = await api(edUrl(E.jid, E.cid));
        if (!E.cid) return;
        E.state.candidate = st.candidate;
        if (RENDERING.includes(st.candidate.status)) return paintState();
        clearInterval(E.pollT); E.busy = false; E.dirty = false; paintHook();
        setBusy(btn, false);
        const v = $("edVideo");
        if (v && st.candidate.has_preview) { v.src = previewSrc(); if (!reduced()) v.play().catch(() => {}); loadTimeline(); }
        else render();
        paintState(st.candidate.status === "failed" ? "Preview render failed: see the clip in Review" : undefined);
      } catch (_) { /* keep polling; the island shows the job state */ }
    }, window.POLL_INTERVAL || 2200);
  }

  // ------------------------------------------------------------------ events (delegated, data-*)
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-ed-back],[data-ed-hook-on],[data-ed-hook-dur],[data-ed-render],[data-ed-play],[data-ed-tab],[data-ed-word],[data-ed-seekarea]");
    if (!t || !E.state && !t.matches("[data-ed-back]")) return;
    if (t.matches("[data-ed-back]")) {
      e.preventDefault(); close(true);
      const q = document.querySelector('[data-nav="queue"]'); if (q) q.click();
      return;
    }
    if (t.matches("[data-ed-hook-on]")) {
      E.hook.on = !E.hook.on;
      const panel = document.querySelector(".ed-panel"); panel.innerHTML = captionsPanel();
      paintHook(); scheduleSave(); return;
    }
    if (t.matches("[data-ed-hook-dur]")) {
      E.hook.duration = Number(t.dataset.edHookDur);
      document.querySelectorAll("[data-ed-hook-dur]").forEach((b) => b.setAttribute("aria-pressed", String(b === t)));
      const v = $("edVideo"); if (v) { v.currentTime = 0; }
      paintHook(); scheduleSave(); return;
    }
    if (t.matches("[data-ed-word]")) { const w = E.tl && E.tl.words[Number(t.dataset.edWord)]; if (w) seek(w.start + 0.001); return; }
    if (t.matches("[data-ed-seekarea]")) {                  // click on the ruler/waveform, not a chip
      const r = t.getBoundingClientRect(); seek((e.clientX - r.left) / PPS); return;
    }
    if (t.matches("[data-ed-render]")) return renderPreview(t);
    if (t.matches("[data-ed-play]")) { const v = $("edVideo"); if (v) v.paused ? v.play() : v.pause(); return; }
    if (t.matches("[data-ed-tab]") && t.getAttribute("aria-disabled") !== "true") {
      E.tab = t.dataset.edTab;
      document.querySelectorAll("[data-ed-tab]").forEach((b) => b.setAttribute("aria-selected", String(b === t)));
      moveSeg();
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.id !== "edHookText" || !E.state) return;
    E.hook.text = e.target.value;
    const v = $("edVideo"); if (v && v.currentTime > Number(E.hook.duration)) v.currentTime = 0;
    paintHook(); scheduleSave();
  });
  // Stepper / tab-bar navigation while the editor is open: leave the editor first (capture phase,
  // so index.html's own handler then shows the chosen view normally).
  document.addEventListener("click", (e) => {
    if (E.cid && e.target.closest("[data-nav],[data-flow-editor]")) close(true);
  }, true);
  window.addEventListener("hashchange", route);
  window.addEventListener("resize", () => { if (E.cid) moveSeg(); }, { passive: true });
  window.addEventListener("load", () => setTimeout(route, 0));
  window.clipflowEditor = { open: (jid, cid) => { location.hash = `#editor/${jid}/${cid}`; }, close };
})();
