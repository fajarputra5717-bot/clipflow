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
  const READY_TABS = new Set(["captions", "effects", "audio"]);   // Watermark / Export arrive later
  const edUrl = (jid, cid) => `/api/jobs/${encodeURIComponent(jid)}/candidates/${encodeURIComponent(cid)}/editor`;
  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PPS = 100;                              // timeline pixels per second
  const ZOOM_SPAN = 1.75;                       // ramp 0.25 + hold 1.0 + ramp 0.25 + merge gap: retention.plan_zoom_windows
  const E = { zoom: { on: true, intensity: 50, markers: [] }, zoomT: 0, mode: "seek", cuts: { trim: null, removed: [] }, cutT: 0, drag: null, tl: null, raf: 0, nowWord: -1, jid: null, cid: null, state: null, hook: null, saveT: 0, pollT: 0, hidden: [], tab: "captions", busy: false };

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
      E.cuts = { trim: E.state.cuts.trim, removed: E.state.cuts.removed.map((r) => r.slice()) };
      E.mode = "seek";
      E.zoom = { on: E.state.zoom.on, intensity: E.state.zoom.intensity, markers: E.state.zoom.markers.slice() };
      E.progress = { on: E.state.progress.on, color: E.state.progress.color };
      E.audio = { compress: E.state.audio.compress, silence_trim: E.state.audio.silence_trim,
                  silence_ranges: (E.state.audio.silence_ranges || []).map((r) => r.slice()) };
      loadCaptions();
      render();
      if (RENDERING.includes(E.state.candidate.status)) watchRender();
    } catch (e) {
      s.innerHTML = `<div class="panel error-box">Can't open this clip: ${esc(e.message)} <a href="#" data-ed-back>Back</a></div>`;
    }
  }

  function close(setHash = true) {
    clearTimeout(E.saveT); clearTimeout(E.cutT); clearTimeout(E.zoomT); clearInterval(E.pollT); cancelAnimationFrame(E.raf); E.tl = null; E.nowWord = -1; E.drag = null;
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
        <a class="ed-back" href="#review/${esc(E.jid)}" data-ed-back>← Review</a>
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
            <div class="ed-prog" id="edProg" aria-hidden="true"><i></i></div>
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
          <div class="ed-panel" role="tabpanel" aria-labelledby="edtab-${E.tab}">${panelHtml(E.tab)}</div>
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
    const chip = (cls, data, a, b, label, title) => `<button type="button" class="${cls}" ${data} title="${esc(title)}"
        style="left:${(a * PPS).toFixed(1)}px;width:${Math.max(14, (b - a) * PPS - 2).toFixed(1)}px">${esc(label)}</button>`;
    const words = tl.words.map((w) => chip("ed-word", `data-ed-word="${w.i}"`, w.start, w.end, w.text, `${w.text} · ${w.start.toFixed(2)} s`)).join("");
    const pauses = (tl.gaps || []).map((g, k) => chip("ed-word ed-pause" + (g.end - g.start >= E.state.cuts.suggest_min_gap ? " suggest" : ""),
      `data-ed-pause="${k}"`, g.start, g.end, `${(g.end - g.start).toFixed(1)}s`, `Pause ${(g.end - g.start).toFixed(2)} s`)).join("");
    const nSuggest = suggestedPauses().length;
    el.innerHTML = `
      <div class="ed-tl-head"><span class="ed-label">Timeline</span>
        <div class="ed-chips" role="group" aria-label="Click mode">
          <button type="button" class="ed-chip" data-ed-mode="seek" aria-pressed="${E.mode === "seek"}">Seek</button>
          <button type="button" class="ed-chip" data-ed-mode="cut" aria-pressed="${E.mode === "cut"}" title="Cut mode (C)">✂ Cut</button>
          <button type="button" class="ed-chip" data-ed-mode="zoom" aria-pressed="${E.mode === "zoom"}" title="Zoom mode (Z): click the timeline to add a punch-in, click a ◆ to remove it">◆ Zoom</button>
        </div>
        <button type="button" class="ed-chip" data-ed-suggest ${nSuggest ? "" : "disabled"}>Cut ${nSuggest} pause${nSuggest === 1 ? "" : "s"} ≥ ${E.state.cuts.suggest_min_gap} s</button>
        <button type="button" class="ed-chip" data-ed-fillers ${(tl.fillers || []).length ? "" : "hidden"}></button>
        <button type="button" class="ed-chip" data-ed-cuts-reset>Restore all</button>
        <button type="button" class="ed-chip" data-ed-zoom-add title="Add a punch-in at the playhead (Z mode: click anywhere)">+ Zoom at playhead</button>
        <span class="ed-spacer"></span>
        <span class="ed-out" id="edOut"></span>
        <span class="ed-time" id="edTlTime">0:00.0 / ${fmt(dur)}</span></div>
      <div class="ed-hint" id="edTlHint"></div>
      <div class="ed-tl-scroll" id="edTlScroll">
        <div class="ed-tl-inner" id="edTlInner" style="width:${W}px" data-ed-seekarea>
          <div class="ed-tl-ruler" aria-hidden="true">${ruler}</div>
          <canvas class="ed-tl-wave" id="edWave" aria-hidden="true"></canvas>
          <div id="edBands" aria-hidden="true"></div>
          <div class="ed-zoom-lane" id="edZoomLane" aria-label="Zoom punch-ins"></div>
          <div class="ed-tl-words" role="group" aria-label="Words and pauses">${pauses}${words}</div>
          <div class="ed-trim-shade l" id="edShadeL" aria-hidden="true"></div><div class="ed-trim-shade r" id="edShadeR" aria-hidden="true"></div>
          <div class="ed-trim-h" id="edTrimA" role="slider" tabindex="0" aria-label="Clip start" data-ed-trim="a"></div>
          <div class="ed-trim-h" id="edTrimB" role="slider" tabindex="0" aria-label="Clip end" data-ed-trim="b"></div>
          <div class="ed-tl-playhead" id="edPlayhead" aria-hidden="true"></div>
        </div>
      </div>
      ${tl.peaks ? "" : `<div class="ed-hint">The waveform appears after the next Render preview.</div>`}`;
    drawWave();
    paintCuts();
    paintPlayhead();
  }

  // ---- cuts (task 3): source-time ranges; the rendered preview's keep maps video ↔ timeline
  const PAD = () => (E.state && E.state.cuts.pad) || 0.12;
  function trimWin() { return E.cuts.trim || [0, E.tl ? E.tl.duration : 0]; }
  function covered(a, b) { return E.cuts.removed.some(([s, e]) => s <= a + 0.02 && e >= b - 0.02); }
  const ms = (x) => Math.round(x * 1000) / 1000;
  function merge(rs) {
    const out = [];
    rs.map(([s, e]) => [ms(s), ms(e)]).sort((x, y) => x[0] - y[0]).forEach(([s, e]) => {
      if (out.length && s <= out[out.length - 1][1] + 0.001) out[out.length - 1][1] = Math.max(out[out.length - 1][1], e);
      else out.push([s, e]);
    });
    return out;
  }
  function subtract(rs, a, b) {
    const out = [];
    rs.forEach(([s, e]) => { if (e <= a || s >= b) out.push([s, e]); else { if (s < a) out.push([s, a]); if (e > b) out.push([b, e]); } });
    return out.filter(([s, e]) => e - s >= 0.04);
  }
  function pauseRange(g) {
    const p = PAD();
    return g.end - g.start > 2 * p + 0.08 ? [g.start + p, g.end - p] : [g.start, g.end];
  }
  function suggestedPauses() {
    if (!E.tl) return [];
    const [lo, hi] = trimWin();
    return (E.tl.gaps || []).filter((g) => g.end - g.start >= E.state.cuts.suggest_min_gap && g.start >= lo && g.end <= hi
      && g.start > 0.01 && g.end < E.tl.duration - 0.01 && !covered(...pauseRange(g)));   // inner pauses only (edges = trim)
  }
  // 5b: filler words (shared/languages.py lists, server-side per job language) = suggestions only
  function pendingFillers() {
    if (!E.tl) return [];
    const [lo, hi] = trimWin();
    return (E.tl.fillers || []).filter((f) => f.start >= lo - 0.01 && f.end <= hi + 0.01 && !covered(f.start, f.end));
  }
  function fillerOf(i) {
    return (E.tl && E.tl.fillers || []).find((f) => i >= f.i0 && i <= f.i1);
  }
  function plannedKeep() {
    const [lo, hi] = trimWin();
    let keep = [[lo, hi]];
    E.cuts.removed.forEach(([s, e]) => { keep = subtract(keep, s, e); });
    return keep;
  }
  const outputSeconds = () => plannedKeep().reduce((a, [s, e]) => a + e - s, 0);
  function toggleRange(a, b) {
    E.cuts.removed = covered(a, b) ? subtract(E.cuts.removed, a, b) : merge([...E.cuts.removed, [a, b]]);
    cutsChanged();
  }
  function cutsChanged() {
    paintCuts();
    E.dirty = true; paintHook();
    clearTimeout(E.cutT);
    paintState("Saving…");
    E.cutT = setTimeout(saveCuts, 600);
  }
  async function saveCuts() {
    clearTimeout(E.cutT); E.cutT = 0;
    try {
      E.state = await api(edUrl(E.jid, E.cid) + "/cuts", { method: "PUT", body: JSON.stringify({ trim: E.cuts.trim, removed: E.cuts.removed }) });
      paintState();
    } catch (e) { paintState("Not saved: " + e.message); throw e; }
  }

  function paintCuts() {
    if (!E.tl || !$("edTlInner")) return;
    const [lo, hi] = trimWin(), dur = E.tl.duration;
    document.querySelectorAll("[data-ed-word]").forEach((b) => {
      const w = E.tl.words[Number(b.dataset.edWord)], f = fillerOf(Number(b.dataset.edWord));
      const isCut = covered(w.start, w.end) || w.end <= lo + 0.01 || w.start >= hi - 0.01;
      b.classList.toggle("cut", isCut);
      b.classList.toggle("filler-suggest", !!f && !isCut && !covered(f.start, f.end));
      if (f) b.title = `${w.text} · filler “${f.text}” · ${isCut ? "cut" : "suggested cut: accept with “Cut fillers” or click in ✂ Cut mode"}`;
    });
    const fb = document.querySelector("[data-ed-fillers]"), nf = pendingFillers().length;
    if (fb) { fb.disabled = !nf; fb.textContent = `Cut ${nf} filler${nf === 1 ? "" : "s"}`; }
    document.querySelectorAll("[data-ed-pause]").forEach((b) => {
      const g = E.tl.gaps[Number(b.dataset.edPause)];
      b.classList.toggle("cut", covered(...pauseRange(g)) || g.end <= lo + 0.01 || g.start >= hi - 0.01);
    });
    $("edBands").innerHTML = E.cuts.removed.map(([s, e]) => `<div class="ed-cut-band" style="left:${s * PPS}px;width:${(e - s) * PPS}px"></div>`).join("");
    $("edShadeL").style.width = lo * PPS + "px";
    $("edShadeR").style.width = Math.max(0, dur - hi) * PPS + "px";
    [["edTrimA", lo], ["edTrimB", hi]].forEach(([id, v]) => {
      const h = $(id); h.style.left = v * PPS + "px";
      h.setAttribute("aria-valuenow", v.toFixed(1)); h.setAttribute("aria-valuemin", "0"); h.setAttribute("aria-valuemax", dur.toFixed(1));
      h.setAttribute("aria-valuetext", `${v.toFixed(1)} seconds`);
    });
    const out = outputSeconds(), o = $("edOut");
    if (o) o.textContent = `Output ${out.toFixed(1)} s`;
    paintZoom();
    const hint = $("edTlHint");
    if (hint) hint.textContent = E.mode === "zoom" ? `Zoom mode: click the timeline to add a punch-in (max ${E.state.zoom.max_markers}), click a ◆ to remove it.`
      : E.mode === "cut" ? "Cut mode: click a word or pause to cut it, click again to restore. Drag the orange handles to trim."
      : (E.state.candidate.has_preview ? "Click a word to jump there. Switch to ✂ Cut (C) to cut words and pauses." : "Render a preview to play.");
    const s = document.querySelector("[data-ed-suggest]"), n = suggestedPauses().length;
    if (s) { s.disabled = !n; s.textContent = `Cut ${n} pause${n === 1 ? "" : "s"} ≥ ${E.state.cuts.suggest_min_gap} s`; }
  }

  // ---- zoom punch-ins (task 4): source-time markers, rendered before captions/watermark
  function paintZoom() {
    const lane = $("edZoomLane"); if (!lane || !E.tl) return;
    const dur = E.tl.duration;
    lane.innerHTML = E.zoom.markers.map((m, k) => `<span class="ed-zoom-span" style="left:${m * PPS}px;width:${Math.min(ZOOM_SPAN, dur - m) * PPS}px" aria-hidden="true"></span>
      <button type="button" class="ed-zoom-mark" data-ed-zoom-mark="${k}" style="left:${m * PPS}px" title="Punch-in at ${m.toFixed(2)} s · click to remove" aria-label="Zoom punch-in at ${m.toFixed(1)} seconds, remove"></button>`).join("");
    const b = document.querySelector("[data-ed-zoom-add]");
    if (b) b.disabled = E.zoom.markers.length >= E.state.zoom.max_markers;
  }
  function addZoom(t) {
    if (!E.tl || E.zoom.markers.length >= E.state.zoom.max_markers) return;
    t = Math.round(Math.max(0, Math.min(t, E.tl.duration - 0.3)) * 100) / 100;
    if (E.zoom.markers.some((m) => Math.abs(m - t) < 0.3)) return;          // a second click on the same spot
    E.zoom.markers = [...E.zoom.markers, t].sort((a, b) => a - b);
    zoomChanged();
  }
  function zoomChanged() {
    paintZoom(); E.dirty = true; paintHook();
    clearTimeout(E.zoomT); paintState("Saving…");
    E.zoomT = setTimeout(saveZoom, 600);
  }
  async function saveZoom() {
    clearTimeout(E.zoomT); E.zoomT = 0;
    try {
      E.state = await api(edUrl(E.jid, E.cid) + "/zoom", { method: "PUT", body: JSON.stringify(E.zoom) });
      paintState();
    } catch (e) { paintState("Not saved: " + e.message); throw e; }
  }

  function setTrim(which, v) {
    const [lo, hi] = trimWin(), dur = E.tl.duration, MIN = 1;
    let a = lo, b = hi;
    if (which === "a") a = Math.max(0, Math.min(v, b - MIN)); else b = Math.min(dur, Math.max(v, a + MIN));
    a = Math.round(a * 100) / 100; b = Math.round(b * 100) / 100;
    E.cuts.trim = a <= 0.005 && b >= dur - 0.005 ? null : [a, b];
    E.cuts.removed = E.cuts.removed.map(([s, e]) => [Math.max(s, a), Math.min(e, b)]).filter(([s, e]) => e - s >= 0.04);
  }

  // rendered preview's keep (source time) ↔ video time
  function toOut(t) {
    const keep = E.tl && E.tl.keep;
    if (!keep) return t;
    let acc = 0;
    for (const [a, b] of keep) { if (t < b) return acc + Math.max(0, t - a); acc += b - a; }
    return acc;
  }
  function toSrc(o) {
    const keep = E.tl && E.tl.keep;
    if (!keep) return o;
    let acc = 0;
    for (const [a, b] of keep) { if (o <= acc + (b - a)) return a + (o - acc); acc += b - a; }
    return keep.length ? keep[keep.length - 1][1] : o;
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
    const t = toSrc(v ? v.currentTime : 0), x = t * PPS;
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
    v.currentTime = Math.max(0, Math.min(toOut(t), v.duration || toOut(t)));
    paintPlayhead(false); paintHook();
  }

  function panelHtml(tab) { return tab === "effects" ? effectsPanel() : tab === "audio" ? audioPanel() : captionsPanel(); }
  const sw = (attr, on, label) => `<button class="ed-switch" type="button" role="switch" aria-checked="${on}" aria-label="${label}" ${attr}></button>`;

  function effectsPanel() {
    const z = E.zoom, p = E.progress, n = z.markers.length;
    return `
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Zoom punch-ins</div>
          <div class="ed-hint">${n} punch-in${n === 1 ? "" : "s"} on the timeline: add them in ◆ Zoom mode (key Z).</div></div>
          ${sw("data-ed-zoom-on", z.on, "Zoom punch-ins")}</div>
        <div class="ed-dep ${z.on ? "" : "is-off"}" ${z.on ? "" : "inert"}>
          <label class="ed-range"><span>Intensity</span>
            <input type="range" min="0" max="100" step="5" value="${z.intensity}" data-ed-zoom-intensity aria-label="Zoom intensity">
            <output id="edZoomOut">${z.intensity}%</output></label>
        </div>
      </div>
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Progress bar</div><div class="ed-hint">Thin bar across the top; it runs on through cuts.</div></div>
          ${sw("data-ed-progress-on", p.on, "Progress bar")}</div>
        <div class="ed-dep ${p.on ? "" : "is-off"}" ${p.on ? "" : "inert"}>
          <div class="ed-swatches" role="group" aria-label="Progress bar colour">
            ${E.state.progress.colors.map((c) => `<button type="button" class="ed-sw" style="background:${c}" data-ed-progress-color="${c}"
               aria-pressed="${c === p.color}" aria-label="Colour ${c}"></button>`).join("")}
          </div>
        </div>
      </div>`;
  }

  function audioPanel() {
    const a = E.audio, sugg = E.tl ? suggestedPauses() : [];
    const applied = a.silence_ranges.reduce((t, [s, e]) => t + (e - s), 0);
    const silenceHint = a.silence_trim ? `${a.silence_ranges.length} pause${a.silence_ranges.length === 1 ? "" : "s"} cut, ${applied.toFixed(1)} s saved. Restore any on the timeline.`
      : `${sugg.length} pause${sugg.length === 1 ? "" : "s"} ≥ ${E.state.cuts.suggest_min_gap} s found in the speech. Off by default.`;
    const L = E.state.audio.loudness;
    return `
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Remove silences</div><div class="ed-hint" id="edSilenceHint">${silenceHint}</div></div>
          ${sw("data-ed-silence", a.silence_trim, "Remove silences")}</div>
      </div>
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Light compression</div>
          <div class="ed-hint">Evens out loud peaks (shouts, laughs) before loudness normalisation.</div></div>
          ${sw("data-ed-compress", a.compress, "Light compression")}</div>
      </div>
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Loudness</div>
          <div class="ed-hint">Normalised to ${L.lufs} LUFS with a ${L.true_peak_dbtp} dBTP limiter on every preview and final. Always on.</div></div>
          <span class="badge completed">Always on</span></div>
      </div>`;
  }

  // One debounced save per editor key. Editor routes (relative url) answer the editor state; main's own
  // routes (absolute url, e.g. the candidate PATCH) don't, so their answer is ignored.
  function saver(key, url, getBody, method = "PUT") {
    E.savers = E.savers || {};
    const s = E.savers[key] = E.savers[key] || { t: 0 };
    s.flush = async () => {
      clearTimeout(s.t); s.t = 0;
      try {
        const body = getBody();
        if (body === null) return paintState();
        const r = await api(url.startsWith("/api/") ? url : edUrl(E.jid, E.cid) + url, { method, body: JSON.stringify(body) });
        if (!url.startsWith("/api/")) E.state = r;
        if (s.after) s.after();
        paintState();
      }
      catch (e) { paintState("Not saved: " + e.message); throw e; }
    };
    clearTimeout(s.t); E.dirty = true; paintHook(); paintState("Saving…");
    s.t = setTimeout(s.flush, 600);
  }
  async function flushSavers() {
    for (const s of Object.values(E.savers || {})) if (s.t) await s.flush();
  }
  const saveProgress = () => saver("progress", "/progress", () => E.progress);
  const saveAudio = () => saver("audio", "/audio", () => E.audio);
  function repaintPanel() { const p = document.querySelector(".ed-panel"); if (p) p.innerHTML = panelHtml(E.tab); }

  // ------------------------------------------------------------------ captions (task 7a)
  // Style + animation are this clip's own (edit_spec.caption, cleared when equal to the job's, 108);
  // font + size are the job's (every clip in it); position, keywords and caption text are the clip's.
  const kwToken = (w) => String(w || "").toLowerCase().replace(/[^\p{L}\p{N}_]+/gu, "");
  const normText = (t) => String(t || "").toUpperCase().split("\n").map((l) => l.trim().replace(/\s+/g, " ")).filter(Boolean).join("\n");
  function loadCaptions() {
    const c = E.state.captions;
    E.cap = { style: c.style, animation: c.animation, font: c.job.font, size: c.job.size, caption_y: c.caption_y,
              keywords: new Set(c.keywords), keyword_color: c.keyword_color, text: normText(c.text),
              savedText: normText(c.text), job: { ...c.job }, styleOpen: E.cap ? E.cap.styleOpen : false };
  }
  const capOpt = () => E.state.captions.options;
  const styleOf = (id) => capOpt().styles.find((x) => x.id === id) || capOpt().styles[0];
  function kwColor() {
    if (E.cap.keyword_color) return E.cap.keyword_color;
    const hi = styleOf(E.cap.style).highlight.replace("#", ""), rgb = (h) => [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    const h = rgb(hi), far = capOpt().keyword_colors.find((k) => { const r = rgb(k.color.slice(1)); return Math.hypot(r[0] - h[0], r[1] - h[1], r[2] - h[2]) >= 120; });
    return (far || capOpt().keyword_colors[0]).color;      // 116: auto = first palette colour that contrasts
  }
  function fontCss(name) {                                   // browser stand-in for the ASS font (served at /fonts/)
    const fam = { Montserrat: "CF Montserrat", Inter: "CF Inter", Oswald: "CF Oswald", Poppins: "CF Poppins" }[String(name).split(" ")[0]];
    const weight = /Black/.test(name) ? 900 : /ExtraBold/.test(name) ? 800 : /Bold|Anton|Bebas|Archivo/.test(name) ? 700 : 500;
    return `font-family:${fam ? `"${fam}",` : ""}var(--font-display);font-weight:${weight}`;
  }
  function sampleHtml(style, kw, words = ["THIS", "CHANGES", "EVERYTHING"]) {
    const st = styleOf(style);
    return `<span class="ed-capsample${st.box ? " is-box" : ""}${st.shadow ? " has-shadow" : ""}" style="--rest:${st.resting};--hi:${st.highlight};--kw:${kw};--ol:${st.outline}px;letter-spacing:${st.letterSpacing}">${
      words.map((w, i) => `<span class="${i === 1 ? "kw" : i === 0 ? "hi" : ""}">${esc(w)}</span>`).join(" ")}</span>`;
  }
  function captionsPanel() {
    const C = E.cap, o = capOpt(), cs = E.state.captions, kw = kwColor();
    const words = [], seen = new Set();
    for (const w of C.text.split(/\s+/)) { const t = kwToken(w); if (t && !seen.has(t)) { seen.add(t); words.push([t, w.replace(/[^\p{L}\p{N}'-]+/gu, "")]); } }
    const presetOn = (p) => p.style === C.style && p.animation === C.animation;
    const yOn = C.caption_y != null, yVal = yOn ? C.caption_y : cs.auto_caption_y;
    return `
      ${cs.burn ? "" : `<div class="ed-note-box">Burn-in is off for this job: captions aren't drawn on the video.</div>`}
      <div class="ed-group">
        <div class="ed-label">Preset</div>
        <div class="ed-presets" role="group" aria-label="Caption preset">
          ${o.presets.map((p) => `<button type="button" class="ed-preset" data-ed-preset="${esc(p.id)}" aria-pressed="${presetOn(p)}">
            <span class="ed-ptile">${sampleHtml(p.style, kw, ["THIS", "CHANGES"])}</span>${esc(p.label)}</button>`).join("")}
        </div>
        <div class="ed-row ed-row-tight"><span class="ed-hint">${C.style === cs.job.style && C.animation === cs.job.animation ? "Same as the job's style." : "This clip only."}</span>
          <button type="button" class="sm" data-ed-cap-all>Apply to all clips</button></div>
      </div>
      <div class="ed-group">
        <div class="ed-row ed-row-tight"><div class="ed-label">Keyword highlight</div>
          <div class="ed-swatches" role="group" aria-label="Keyword colour">${o.keyword_colors.map((k) => `<button type="button" class="ed-sw ed-sw-sm" style="background:${k.color}"
            data-ed-kw-color="${k.color}" aria-label="${esc(k.label)}" title="${esc(k.label)}" aria-pressed="${kw === k.color}"></button>`).join("")}</div></div>
        <div class="ed-hint" id="edKwNote">${C.keywords.size ? `${C.keywords.size} highlighted · tap a word to toggle` : "Tap a word to highlight it"}</div>
        <div class="ed-kw" role="group" aria-label="Caption words: tap to highlight" style="--kw:${kw}">
          ${words.slice(0, 80).map(([t, w]) => `<button type="button" class="ed-kwword" data-ed-kw="${esc(t)}" aria-pressed="${C.keywords.has(t)}">${esc(w)}</button>`).join("")}
        </div>
      </div>
      ${hookGroupHtml()}
      <div class="ed-group">
        <div class="ed-row ed-row-tight"><label class="ed-label" for="edCapText">Caption text</label>
          <button type="button" class="sm" data-ed-fix-typos>Fix typos (AI)</button></div>
        <textarea id="edCapText" class="ed-captext" rows="5" spellcheck="false" data-ed-cap-text aria-describedby="edCapTextHint">${esc(C.text)}</textarea>
        <div class="ed-row ed-row-tight"><span class="ed-hint" id="edCapTextHint">One caption line per row. Edited words keep Whisper's timing.</span>
          ${normText(C.text) !== normText(cs.transcript) ? `<button type="button" class="sm" data-ed-cap-reset>Back to transcript</button>` : ""}</div>
      </div>
      <details class="ed-group ed-more" data-ed-style-more ${C.styleOpen ? "open" : ""}>
        <summary class="ed-label">Style, font, size and position</summary>
        <div class="ed-sample">${sampleHtml(C.style, kw)}</div>
        <label class="ed-field"><span>Style</span><select data-ed-cap="style">${o.styles.map((x) => `<option value="${x.id}" ${x.id === C.style ? "selected" : ""}>${esc(x.label)}</option>`).join("")}</select></label>
        <label class="ed-field"><span>Animation</span><select data-ed-cap="animation">${o.animations.map((x) => `<option value="${x.id}" ${x.id === C.animation ? "selected" : ""}>${esc(x.label)}</option>`).join("")}</select></label>
        <label class="ed-field"><span>Font · all clips in this job</span><select data-ed-cap="font">${o.fonts.map((f) => `<option ${f === C.font ? "selected" : ""}>${esc(f)}</option>`).join("")}</select></label>
        <label class="ed-range"><span>Size · job</span><input type="range" min="${o.size_range[0]}" max="${o.size_range[1]}" step="1" value="${C.size}" data-ed-cap="size" aria-label="Caption size"><output id="edCapSize">${C.size}</output></label>
        <div class="ed-row"><div><div class="ed-label" id="edCapYLbl">Custom position</div>
          <div class="ed-hint">% from the top. Lower moves captions up, off in-game HUD. With a facecam panel they stay above it.</div></div>
          <button class="ed-switch" type="button" role="switch" aria-checked="${yOn}" aria-labelledby="edCapYLbl" data-ed-capy-on></button></div>
        <label class="ed-range ${yOn ? "" : "is-off"}"><span>Position</span><input type="range" min="${o.caption_y_range[0]}" max="${o.caption_y_range[1]}" step="1" value="${yVal}"
          data-ed-capy aria-label="Caption position" ${yOn ? "" : "disabled"}><output id="edCapY">${yOn ? `${yVal} %` : "Auto"}</output></label>
      </details>
      <div class="ed-group">
        <div class="ed-row"><div><div class="ed-label">Different moment</div>
          <div class="ed-hint">AI picks another hook from the video and re-renders this clip. Cuts, punch-ins and highlighted keywords are cleared; style choices stay.</div></div>
          <button type="button" class="sm" data-ed-new-hook>Get another hook</button></div>
      </div>`;
  }
  function hookGroupHtml() {
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
  // Clip-level caption fields → one candidate PATCH (edit_spec merge + subtitle_override when the text changed).
  function capClipBody() {
    const C = E.cap, job = E.state.captions.job, spec = {
      caption: C.style === job.style && C.animation === job.animation ? null : { style: C.style, animation: C.animation },
      caption_y: C.caption_y,
    };
    if (C.kwDirty) { spec.keywords = [...C.keywords]; spec.keyword_color = C.keyword_color || null; }   // untouched: the worker's AI pick (111) stays free
    const body = { edit_spec: spec }, now = normText(C.text);
    if (now !== C.savedText) body.subtitle_override = now === normText(E.state.captions.transcript) ? "" : now;   // "" = back to Whisper
    return body;
  }
  function saveCapClip() {
    saver("capclip", `/api/jobs/${encodeURIComponent(E.jid)}/candidates/${encodeURIComponent(E.cid)}`, capClipBody, "PATCH");
    E.savers.capclip.after = () => { E.cap.savedText = normText(E.cap.text); };
  }
  function saveCapJob() {
    const job = E.state.captions.job;
    job.font = E.cap.font; job.size = E.cap.size;
    saver("capjob", `/api/jobs/${encodeURIComponent(E.jid)}/subtitle-style`, () => ({
      subtitle_style: job.style, subtitle_font: E.cap.font, subtitle_size: E.cap.size, subtitle_animation: job.animation }), "PATCH");
  }
  function repaintCaptions(focusSel) {
    if (E.tab !== "captions") return;
    const ta = $("edCapText"), pos = ta && document.activeElement === ta ? [ta.selectionStart, ta.selectionEnd] : null;
    repaintPanel();
    if (focusSel) { const el = document.querySelector(focusSel); if (el) el.focus({ preventScroll: true }); }
    if (pos) { const t = $("edCapText"); t.focus({ preventScroll: true }); t.setSelectionRange(...pos); }
  }
  // Two-tap confirm for actions that reach beyond this clip's edits (no native dialogs in the app).
  function armed(btn, label) {
    if (btn.dataset.armed === "1") { clearTimeout(btn._armT); btn.dataset.armed = ""; btn.textContent = btn.dataset.label; return true; }
    btn.dataset.label = btn.textContent; btn.dataset.armed = "1"; btn.textContent = label; btn.classList.add("is-armed");
    btn._armT = setTimeout(() => { btn.dataset.armed = ""; btn.textContent = btn.dataset.label; btn.classList.remove("is-armed"); }, 4000);
    return false;
  }
  async function capApplyAll(btn) {
    if (!armed(btn, "Tap again: every clip re-renders")) return;
    btn.classList.remove("is-armed");
    setBusy(btn, true, "Applying…");
    try {
      await flushSavers();
      await api(`/api/jobs/${encodeURIComponent(E.jid)}/caption-preset`, { method: "POST", body: JSON.stringify({ style: E.cap.style, animation: E.cap.animation }) });
      E.state = await api(edUrl(E.jid, E.cid)); loadCaptions(); repaintCaptions();
      if (RENDERING.includes(E.state.candidate.status)) { paintState(); watchRender(); }
    } catch (e) { paintState("Not applied: " + e.message); }
    finally { setBusy(btn, false); }
  }
  async function capFixTypos(btn) {
    setBusy(btn, true, "Fixing typos…");
    try {
      const r = await api(`/api/jobs/${encodeURIComponent(E.jid)}/candidates/${encodeURIComponent(E.cid)}/fix-subtitle-ai`, { method: "POST" });
      if (r && r.subtitle_text) { E.cap.text = normText(r.subtitle_text); repaintCaptions(); saveCapClip(); }
    } catch (e) { paintState("Fix typos failed: " + e.message); }
    finally { setBusy(btn, false); }
  }
  async function capNewHook(btn) {
    if (!armed(btn, "Tap again to replace this clip")) return;
    btn.classList.remove("is-armed");
    setBusy(btn, true, "Finding a hook…");
    try {
      await flushSavers();
      await api(`/api/jobs/${encodeURIComponent(E.jid)}/candidates/${encodeURIComponent(E.cid)}/new-hook`, { method: "POST" });
      E.reloadAfterRender = true;                 // new start/end + transcript: reopen everything once rendered
      E.state.candidate.status = "preview_queued"; paintState(); watchRender();
    } catch (e) { setBusy(btn, false); paintState(e.message); }
  }

  function hookText() { return (E.hook.text || E.hook.default_text || "").trim(); }

  function paintHook() {
    const el = $("edHook"), v = $("edVideo");
    if (!el) return;
    const t = v ? v.currentTime : 0;
    // The rendered preview already has the saved card baked in: the CSS overlay only stands in for
    // changes that aren't rendered yet (otherwise two cards would show).
    const show = !!E.dirty && E.hook.on && !!hookText() && t < Number(E.hook.duration);
    const prog = $("edProg");
    if (prog) {
      const on = !!E.dirty && E.progress && E.progress.on, dur = (v && v.duration) || 0;
      prog.classList.toggle("show", on);
      if (on) { prog.style.setProperty("--prog", E.progress.color); prog.firstElementChild.style.transform = `scaleX(${dur ? Math.min(1, v.currentTime / dur) : 0})`; }
    }
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
    else if (E.dirty) el.textContent = `Changes saved · not rendered yet · output ${outputSeconds().toFixed(1)} s`;
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
      if (E.cutT) await saveCuts();
      if (E.zoomT) await saveZoom();
      await flushSavers();
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
        if (E.reloadAfterRender) { E.reloadAfterRender = false; return open(E.jid, E.cid); }
        const v = $("edVideo");
        if (v && st.candidate.has_preview) { v.src = previewSrc(); if (!reduced()) v.play().catch(() => {}); loadTimeline(); }
        else render();
        paintState(st.candidate.status === "failed" ? "Preview render failed: see the clip in Review" : undefined);
      } catch (_) { /* keep polling; the island shows the job state */ }
    }, window.POLL_INTERVAL || 2200);
  }

  // ------------------------------------------------------------------ events (delegated, data-*)
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-ed-back],[data-ed-hook-on],[data-ed-hook-dur],[data-ed-render],[data-ed-play],[data-ed-tab],[data-ed-zoom-on],[data-ed-progress-on],[data-ed-progress-color],[data-ed-compress],[data-ed-silence],[data-ed-word],[data-ed-pause],[data-ed-mode],[data-ed-suggest],[data-ed-fillers],[data-ed-cuts-reset],[data-ed-zoom-add],[data-ed-zoom-mark],[data-ed-trim],[data-ed-seekarea],[data-ed-preset],[data-ed-cap-all],[data-ed-kw],[data-ed-kw-color],[data-ed-fix-typos],[data-ed-cap-reset],[data-ed-capy-on],[data-ed-new-hook]");
    if (!t || !E.state && !t.matches("[data-ed-back]")) return;
    if (t.matches("[data-ed-back]")) {                       // back to the Review page (step 4) for this job
      e.preventDefault(); const jid = E.jid; close(false); location.hash = `#review/${encodeURIComponent(jid || "")}`;
      return;
    }
    if (t.matches("[data-ed-hook-on]")) {
      E.hook.on = !E.hook.on;
      repaintCaptions("[data-ed-hook-on]");
      paintHook(); scheduleSave(); return;
    }
    if (t.matches("[data-ed-preset]")) {
      const p = capOpt().presets.find((x) => x.id === t.dataset.edPreset); if (!p) return;
      E.cap.style = p.style; E.cap.animation = p.animation; repaintCaptions(`[data-ed-preset="${p.id}"]`); saveCapClip(); return;
    }
    if (t.matches("[data-ed-cap-all]")) return capApplyAll(t);
    if (t.matches("[data-ed-kw]")) {
      const k = t.dataset.edKw; E.cap.kwDirty = true; E.cap.keywords.has(k) ? E.cap.keywords.delete(k) : E.cap.keywords.add(k);
      t.setAttribute("aria-pressed", String(E.cap.keywords.has(k)));
      const n = $("edKwNote"); if (n) n.textContent = E.cap.keywords.size ? `${E.cap.keywords.size} highlighted · tap a word to toggle` : "Tap a word to highlight it";
      saveCapClip(); return;
    }
    if (t.matches("[data-ed-kw-color]")) { E.cap.kwDirty = true; E.cap.keyword_color = t.dataset.edKwColor; repaintCaptions(`[data-ed-kw-color="${t.dataset.edKwColor}"]`); saveCapClip(); return; }
    if (t.matches("[data-ed-fix-typos]")) return capFixTypos(t);
    if (t.matches("[data-ed-cap-reset]")) { E.cap.text = normText(E.state.captions.transcript); repaintCaptions("#edCapText"); saveCapClip(); return; }
    if (t.matches("[data-ed-capy-on]")) {
      E.cap.caption_y = E.cap.caption_y == null ? E.state.captions.auto_caption_y : null;
      repaintCaptions("[data-ed-capy-on]"); saveCapClip(); return;
    }
    if (t.matches("[data-ed-new-hook]")) return capNewHook(t);
    if (t.matches("[data-ed-hook-dur]")) {
      E.hook.duration = Number(t.dataset.edHookDur);
      document.querySelectorAll("[data-ed-hook-dur]").forEach((b) => b.setAttribute("aria-pressed", String(b === t)));
      const v = $("edVideo"); if (v) { v.currentTime = 0; }
      paintHook(); scheduleSave(); return;
    }
    if (t.matches("[data-ed-mode]")) { setMode(t.dataset.edMode); return; }
    if (t.matches("[data-ed-suggest]")) { E.cuts.removed = merge([...E.cuts.removed, ...suggestedPauses().map(pauseRange)]); cutsChanged(); return; }
    if (t.matches("[data-ed-zoom-mark]")) { E.zoom.markers = E.zoom.markers.filter((_, k) => k !== Number(t.dataset.edZoomMark)); zoomChanged(); return; }
    if (t.matches("[data-ed-zoom-add]")) { const v = $("edVideo"); addZoom(toSrc(v ? v.currentTime : 0)); return; }
    if (t.matches("[data-ed-fillers]")) { E.cuts.removed = merge([...E.cuts.removed, ...pendingFillers().map((f) => [f.start, f.end])]); cutsChanged(); return; }
    if (t.matches("[data-ed-cuts-reset]")) { E.cuts = { trim: null, removed: [] }; cutsChanged(); return; }
    if (t.matches("[data-ed-trim]")) return;                       // handles drag (pointer events below)
    if (E.mode === "zoom" && t.matches("[data-ed-word],[data-ed-pause],[data-ed-seekarea]")) {
      const inner = $("edTlInner"); addZoom((e.clientX - inner.getBoundingClientRect().left) / PPS); return;
    }
    if (t.matches("[data-ed-word]")) {
      const w = E.tl && E.tl.words[Number(t.dataset.edWord)]; if (!w) return;
      const f = fillerOf(w.i);
      if (E.mode === "cut") { if (f && !covered(w.start, w.end)) toggleRange(f.start, f.end); else toggleRange(w.start, w.end); }
      else seek(w.start + 0.001);
      return;
    }
    if (t.matches("[data-ed-pause]")) {
      const g = E.tl && E.tl.gaps[Number(t.dataset.edPause)]; if (!g) return;
      if (E.mode === "cut") toggleRange(...pauseRange(g)); else seek(g.start + 0.001);
      return;
    }
    if (t.matches("[data-ed-seekarea]") && E.mode === "seek") {   // click on the ruler/waveform, not a chip
      const r = t.getBoundingClientRect(); seek((e.clientX - r.left) / PPS); return;
    }
    if (t.matches("[data-ed-render]")) return renderPreview(t);
    if (t.matches("[data-ed-play]")) { const v = $("edVideo"); if (v) v.paused ? v.play() : v.pause(); return; }
    if (t.matches("[data-ed-tab]") && t.getAttribute("aria-disabled") !== "true") {
      const order = ["captions", "effects", "audio", "watermark", "export"], from = order.indexOf(E.tab);
      E.tab = t.dataset.edTab;
      document.querySelectorAll("[data-ed-tab]").forEach((b) => b.setAttribute("aria-selected", String(b === t)));
      const panel = document.querySelector(".ed-panel");
      panel.setAttribute("aria-labelledby", "edtab-" + E.tab);
      panel.innerHTML = panelHtml(E.tab);
      panel.classList.remove("in-l", "in-r"); void panel.offsetWidth;
      if (!reduced()) panel.classList.add(order.indexOf(E.tab) > from ? "in-r" : "in-l");
      moveSeg();
      return;
    }
    if (t.matches("[data-ed-zoom-on]")) { E.zoom.on = !E.zoom.on; repaintPanel(); zoomChanged(); return; }
    if (t.matches("[data-ed-progress-on]")) { E.progress.on = !E.progress.on; repaintPanel(); saveProgress(); return; }
    if (t.matches("[data-ed-progress-color]")) { E.progress.color = t.dataset.edProgressColor; repaintPanel(); saveProgress(); return; }
    if (t.matches("[data-ed-compress]")) { E.audio.compress = !E.audio.compress; repaintPanel(); saveAudio(); return; }
    if (t.matches("[data-ed-silence]")) {
      if (!E.audio.silence_trim) {
        const ranges = suggestedPauses().map(pauseRange);
        E.cuts.removed = merge([...E.cuts.removed, ...ranges]);
        E.audio = { ...E.audio, silence_trim: true, silence_ranges: ranges };
      } else {
        E.audio.silence_ranges.forEach(([s, e]) => { E.cuts.removed = subtract(E.cuts.removed, s, e); });
        E.audio = { ...E.audio, silence_trim: false, silence_ranges: [] };
      }
      cutsChanged(); repaintPanel(); saveAudio(); return;
    }
  });
  function setMode(m) {
    E.mode = m;
    document.querySelectorAll("[data-ed-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.edMode === m)));
    const inner = $("edTlInner"); if (inner) { inner.classList.toggle("is-cut", m === "cut"); inner.classList.toggle("is-zoom", m === "zoom"); }
    paintCuts();
  }
  // trim handles: pointer drag (touch too) + arrow keys
  document.addEventListener("pointerdown", (e) => {
    const h = e.target.closest("[data-ed-trim]"); if (!h || !E.tl) return;
    E.drag = h.dataset.edTrim; h.setPointerCapture(e.pointerId); e.preventDefault();
  });
  document.addEventListener("pointermove", (e) => {
    if (!E.drag) return;
    const inner = $("edTlInner"); setTrim(E.drag, (e.clientX - inner.getBoundingClientRect().left) / PPS); paintCuts();
  });
  document.addEventListener("pointerup", () => { if (E.drag) { E.drag = null; cutsChanged(); } });
  document.addEventListener("keydown", (e) => {
    if (!E.state) return;
    const h = e.target.closest && e.target.closest("[data-ed-trim]");
    if (h && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      const [lo, hi] = trimWin(), step = (e.shiftKey ? 1 : 0.1) * (e.key === "ArrowRight" ? 1 : -1);
      setTrim(h.dataset.edTrim, (h.dataset.edTrim === "a" ? lo : hi) + step); cutsChanged(); e.preventDefault(); return;
    }
    if ((e.key === "c" || e.key === "C") && !e.target.closest("input,textarea,select,[contenteditable]") && !e.metaKey && !e.ctrlKey) {
      setMode(E.mode === "cut" ? "seek" : "cut");
    }
    if ((e.key === "z" || e.key === "Z") && !e.target.closest("input,textarea,select,[contenteditable]") && !e.metaKey && !e.ctrlKey) {
      setMode(E.mode === "zoom" ? "seek" : "zoom");
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.matches && e.target.matches("[data-ed-zoom-intensity]") && E.state) {
      E.zoom.intensity = Number(e.target.value); const o = $("edZoomOut"); if (o) o.textContent = `${E.zoom.intensity}%`;
      zoomChanged(); return;
    }
    if (E.state && E.cap && e.target.matches) {
      const k = e.target.matches("[data-ed-cap]") ? e.target.dataset.edCap : null;
      if (e.target.matches("[data-ed-cap-text]")) { E.cap.text = e.target.value; saveCapClip(); return; }
      if (e.target.matches("[data-ed-capy]")) { E.cap.caption_y = Number(e.target.value); $("edCapY").textContent = `${E.cap.caption_y} %`; saveCapClip(); return; }
      if (k === "size") { E.cap.size = Number(e.target.value); $("edCapSize").textContent = E.cap.size; saveCapJob(); return; }
      if (k === "style" || k === "animation") { E.cap[k] = e.target.value; repaintCaptions(`[data-ed-cap="${k}"]`); saveCapClip(); return; }
      if (k === "font") { E.cap.font = e.target.value; saveCapJob(); return; }
    }
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
  // STAGING banner (Lane C): /api/env is open and secret-free; a plain fetch on purpose (works on the
  // login screen too, before any session exists).
  fetch("/api/env").then((r) => (r.ok ? r.json() : null)).then((d) => {
    if (!d || d.env !== "staging" || document.getElementById("stagingBanner")) return;
    const b = document.createElement("div");
    b.id = "stagingBanner"; b.className = "staging-banner"; b.setAttribute("role", "note");
    b.textContent = "STAGING · test data, not production";
    document.body.appendChild(b); document.body.classList.add("is-staging");
  }).catch(() => {});
  document.addEventListener("toggle", (e) => {                 // keep "Style, font…" open across repaints
    if (E.cap && e.target.matches && e.target.matches("[data-ed-style-more]")) E.cap.styleOpen = e.target.open;
  }, true);
  window.addEventListener("hashchange", route);
  window.addEventListener("resize", () => { if (E.cid) moveSeg(); }, { passive: true });
  window.addEventListener("load", () => setTimeout(route, 0));
  window.clipflowEditor = { open: (jid, cid) => { location.hash = `#editor/${jid}/${cid}`; }, close };
})();
