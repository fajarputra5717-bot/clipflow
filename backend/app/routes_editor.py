"""Editor API (lane B, roadmap P4). Mounted by one line in main.py.

Ownership (P1.5): every route takes the caller through ONE dependency, `get_current_user`, which is
main's `current_user(request)` (session cookie / API token, set by the require_user middleware).
Routes live under /api/jobs/{job_id}/candidates/{candidate_id}/editor…, so main's ownership guard
(JOB_PATH_RE → 404 for rows of other users) already covers them; the SQL below ALSO scopes by
`jobs.user_id` (defense in depth, same rule as main: other users' rows are 404, admins included).
Nothing is stored outside the owned job/candidate rows (editor state = clip_candidates.edit_spec).

main.py is imported lazily (inside handlers) to avoid a circular import; its helpers keep one
implementation of auth, the DB connection, json params and the 114 "final outdated" marking.

Routes (all under /api, so the auth middleware applies):
  GET /api/jobs/{jid}/candidates/{cid}/editor              editor state for one clip
  PUT /api/jobs/{jid}/candidates/{cid}/editor/hook-title   {on, text, duration} → edit_spec.hook_title
  GET /api/jobs/{jid}/candidates/{cid}/editor/timeline     waveform peaks + word chips (task 2)
  PUT /api/jobs/{jid}/candidates/{cid}/editor/cuts         {trim, removed} → edit_spec.cuts (task 3)
  PUT /api/jobs/{jid}/candidates/{cid}/editor/zoom         {on, intensity, markers} → edit_spec.zoom (task 4)
  PUT /api/jobs/{jid}/candidates/{cid}/editor/progress     {on, color} → edit_spec.progress (task 5)
  PUT /api/jobs/{jid}/candidates/{cid}/editor/audio        {compress, silence_trim, silence_ranges} (task 5)
Rendering stays on the existing POST /api/jobs/{jid}/candidates/{cid}/regenerate-preview (island
progress via /api/activity, version history).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shared import caption_options
from shared import edit_director
from shared import edit_spec as edit_specs
from shared import fonts
from shared import languages
from shared import timeline as timelines

import os

editor = APIRouter(prefix="/api/jobs/{job_id}/candidates/{candidate_id}/editor", tags=["editor"])
router = APIRouter()   # what main.py includes: the editor routes + /api/env (registered at the end)


def get_current_user(request: Request) -> dict:
    """The caller ({id, username, role, …}); 401 when not signed in. Lane A's P1.5 principal."""
    return _core().current_user(request)


def owner_filter(user: dict, alias: str = "j") -> tuple[str, list]:
    """SQL fragment + params limiting rows to jobs this user owns (main's rule: owner only)."""
    if not user or not user.get("id"):
        return "FALSE", []
    return f"{alias}.user_id = %s", [user["id"]]


def _core():
    from app import main as core  # lazy: main imports this module
    return core


def _load(cur, jid: str, cid: str, user: dict) -> dict:
    """Candidate + its job, owner-scoped. 404 when missing or not this user's (no existence leak)."""
    where, params = owner_filter(user)
    cur.execute(
        f"""
        SELECT c.id::text, c.job_id::text, c.status, c.title, c.manual_title, c.ai_title, c.reason,
               c.start_time, c.end_time, c.duration_seconds, c.edit_spec, c.preview_path, c.final_path,
               c.updated_at, s.title, j.custom_title, j.platform, j.campaign, j.status,
               c.subtitle_text, c.subtitle_override, j.subtitle_style, j.subtitle_font, j.subtitle_size,
               j.subtitle_animation, j.burn_subtitles, c.thumbnail_options, c.thumbnail_path, c.thumbnail_locked,
               j.watermark_width, j.watermark_opacity, c.description, c.submagic_status, c.submagic_preview_url,
               c.submagic_error
        FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
        LEFT JOIN source_videos s ON s.id = j.source_video_id
        WHERE c.id::text = %s AND c.job_id::text = %s AND {where}
        """,
        [cid, jid, *params],
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")
    keys = ["id", "job_id", "status", "title", "manual_title", "ai_title", "reason", "start_time", "end_time",
            "duration_seconds", "edit_spec", "preview_path", "final_path", "updated_at", "job_source_title",
            "job_custom_title", "platform", "campaign", "job_status", "subtitle_text", "subtitle_override",
            "subtitle_style", "subtitle_font", "subtitle_size", "subtitle_animation", "burn_subtitles",
            "thumbnail_options", "thumbnail_path", "thumbnail_locked", "watermark_width", "watermark_opacity",
            "description", "submagic_status", "submagic_preview_url", "submagic_error"]
    c = dict(zip(keys, row))
    try:   # 112: what "Auto" caption position means for a full-frame clip (the owner's setting)
        c["auto_caption_y"] = float(_core().runtime_setting("FULLFRAME_CAPTION_Y", user_id=user["id"]) or 78)
    except (TypeError, ValueError):
        c["auto_caption_y"] = 78.0
    for key, default in (("WATERMARK_WIDTH", 320), ("WATERMARK_OPACITY", 1.0)):   # the owner's global default
        try:
            c["default_" + key.lower()] = float(_core().runtime_setting(key, user_id=user["id"]) or default)
        except (TypeError, ValueError):
            c["default_" + key.lower()] = float(default)
    return c


def _state(c: dict) -> dict:
    spec = c["edit_spec"] if isinstance(c["edit_spec"], dict) else {}
    default_text = (c["manual_title"] or c["title"] or c["ai_title"] or "").strip()
    ht = edit_specs.hook_title_of(spec) or {}
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0)) or None
    return {
        "job": {"id": c["job_id"], "title": c["job_custom_title"] or c["job_source_title"], "platform": c["platform"],
                "campaign": c["campaign"], "status": c["job_status"]},
        "candidate": {
            "id": c["id"], "status": c["status"], "title": default_text, "reason": c["reason"],
            "duration": round(float(duration), 2) if duration else None,
            "has_preview": bool(c["preview_path"]), "has_final": bool(c["final_path"]),
            "preview_url": f"/api/jobs/{c['job_id']}/candidates/{c['id']}/preview",
            "editor_url": f"/api/jobs/{c['job_id']}/candidates/{c['id']}/editor",
            "updated_at": c["updated_at"].isoformat() if c["updated_at"] else None,
            "edit_spec": spec,
        },
        "cuts": _cuts_state(spec, duration),
        "zoom": {**{"on": True, "intensity": edit_specs.ZOOM_DEFAULT_INTENSITY, "markers": []},
                 **(edit_specs.zoom_of(spec) or {}), "max_markers": edit_specs.ZOOM_MAX_MARKERS},
        "progress": {"on": False, "color": edit_specs.PROGRESS_COLORS[0], **((spec or {}).get("progress") or {}),
                     "colors": list(edit_specs.PROGRESS_COLORS)},
        "audio": {"compress": False, "loud": False, "silence_trim": False, "silence_ranges": [], **edit_specs.audio_of(spec),
                  "loudness": {"lufs": -14.0, "true_peak_dbtp": -1.0, "always_on": True}},
        "captions": _captions_state(c, spec),
        "thumbnail": _thumbnail_state(c),
        "watermark": _watermark_state(c),
        "export": _export_state(c),
        "director": _director_state(spec, c),
        "hook_title": {
            "on": bool(ht.get("on", False)), "text": ht.get("text", ""),
            "duration": ht.get("duration", edit_specs.HOOK_TITLE_DEFAULT_DURATION),
            "default_text": default_text, "durations": list(edit_specs.HOOK_TITLE_DURATIONS),
            "max_chars": edit_specs.HOOK_TITLE_MAX_CHARS,
        },
    }


def _captions_state(c: dict, spec: dict) -> dict:
    """Task 7a: job style (font/size shared by every clip in the job) + this clip's own preset override,
    position, keywords and caption text. Writes go through main's existing routes (candidate PATCH,
    PATCH …/subtitle-style, POST …/caption-preset, fix-subtitle-ai, new-hook)."""
    js = c.get("subtitle_style") if isinstance(c.get("subtitle_style"), dict) else {}
    job_style = js.get("style") or "outline"
    job_anim = c.get("subtitle_animation") or js.get("animation") or "karaoke"
    o_style, o_anim = edit_specs.caption_override(spec)
    own = {"style": o_style, "animation": o_anim} if (o_style or o_anim) else None
    style = o_style or job_style
    override = c.get("subtitle_override") or ""
    return {
        "job": {"style": job_style, "animation": job_anim,
                "font": c.get("subtitle_font") or js.get("font") or fonts.DEFAULT_CAPTION_FONT,
                "size": int(c.get("subtitle_size") or js.get("size") or 42)},
        "clip": own,                                   # None = follows the job's style + animation
        "style": style, "animation": o_anim or job_anim,
        "caption_y": spec.get("caption_y"), "auto_caption_y": c.get("auto_caption_y", 78.0),
        "keywords": list(spec.get("keywords") or []), "keyword_color": spec.get("keyword_color"),
        "auto_keyword_color": caption_options.auto_keyword_color(style),
        "transcript": c.get("subtitle_text") or "", "override": override,
        "text": override or (c.get("subtitle_text") or ""),
        "burn": c.get("burn_subtitles") is not False,
        "options": caption_options.options(),
    }


def _thumbnail_state(c: dict) -> dict:
    """Task 7b: AI + uploaded options (one list, picked the same way), which one is picked, and whether the
    pick is locked (renders then keep it). Writes: main's generate-thumbnails-ai, thumbnail-upload and the
    candidate PATCH selected_thumbnail_index (sets thumbnail_path + thumbnail_locked)."""
    opts = c.get("thumbnail_options") if isinstance(c.get("thumbnail_options"), list) else []
    base = f"/api/jobs/{c['job_id']}/candidates/{c['id']}"
    picked = next((i for i, p in enumerate(opts) if p and p == c.get("thumbnail_path")), None)
    return {
        "options": [{"index": i, "url": f"{base}/thumbnail-options/{i}"} for i in range(len(opts))],
        "picked": picked if c.get("thumbnail_locked") else None,
        "locked": bool(c.get("thumbnail_locked")),
        "current_url": f"{base}/thumbnail" if c.get("thumbnail_path") else None,
        "generating": c.get("status") in ("thumbnail_queued", "thumbnail_rendering"),
    }


def _watermark_state(c: dict) -> dict:
    """Task 7c: the job-level size/opacity (shared by every clip of the job; NULL = the owner's global
    setting). Writes: main's PATCH …/render-options (marks finals outdated)."""
    w, o = c.get("watermark_width"), c.get("watermark_opacity")
    return {"width": int(w if w is not None else c["default_watermark_width"]),
            "opacity": round(float(o if o is not None else c["default_watermark_opacity"]), 2),
            "custom": w is not None or o is not None}


def _export_state(c: dict) -> dict:
    """Task 7d: burn-in toggle (job), description, Submagic pass. Writes go through main's routes
    (render-options, candidate PATCH, generate-description, submagic/*, versions, approve)."""
    return {"burn": c.get("burn_subtitles") is not False, "description": c.get("description") or "",
            "submagic": {"status": c.get("submagic_status"), "preview_url": c.get("submagic_preview_url"),
                         "error": c.get("submagic_error")}}


def _director_state(spec: dict, c: dict) -> dict:
    """Auto Edit E1: the plan (empty until generated) + which effects render today. frames_ready = the current
    preview has sampled frames (a plan made before them has vision false: the UI suggests regenerating)."""
    d = edit_specs.director_of(spec) or {"items": []}
    frames_ready = (_core().DATA_ROOT / "previews" / f"{c['id']}.frame-0.jpg").is_file()
    return {**d, "rendered": sorted(edit_director.RENDERED_EFFECTS), "arrives_in": edit_director.ARRIVES_IN,
            "min_gap": edit_director.MIN_GAP, "frames_ready": frames_ready}


def _cuts_state(spec: dict, duration) -> dict:
    cuts = edit_specs.cuts_of(spec) or {}
    d = float(duration or 0)
    trim = cuts.get("trim") or [0.0, d]
    removed = cuts.get("removed") or []
    out = (trim[1] - trim[0]) - sum(e - s for s, e in removed)
    return {"trim": cuts.get("trim"), "removed": removed, "output_seconds": round(max(0.0, out), 2),
            "suggest_min_gap": 0.6, "pad": 0.12}


def _save_spec_key(job_id, candidate_id, user, key, value):
    """Merge one edit_spec key (None = remove) for an owned, idle clip; 114 outdated-final mark."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
        if c["status"] in ("preview_queued", "preview_rendering", "render_queued", "rendering"):
            raise HTTPException(status_code=409, detail="This clip is rendering; try again when it's done")
        before = (c["edit_spec"] or {}).get(key) if isinstance(c["edit_spec"], dict) else None
        where, params = owner_filter(user)
        cur.execute(
            f"""
            UPDATE clip_candidates c
            SET edit_spec = NULLIF((COALESCE(c.edit_spec, '{{}}'::jsonb) || %s::jsonb) - %s::text[], '{{}}'::jsonb),
                updated_at = NOW()
            FROM jobs j
            WHERE c.id::text = %s AND c.job_id::text = %s AND j.id = c.job_id AND {where}
            """,
            [core.json_param({key: value} if value is not None else {}), [] if value is not None else [key],
             candidate_id, job_id, *params],
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=404, detail="Clip not found")
        if value != before:
            core.mark_finals_outdated(cur, c["job_id"], candidate_id)  # 114: same transaction
        conn.commit()
        return _state(_load(cur, job_id, candidate_id, user))


# --------------------------------------------------------------------------- routes

@editor.get("")
def editor_state(job_id: str, candidate_id: str, user: dict = Depends(get_current_user)):
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
        state = _state(c)
        # 162: campaign label for the Editor header ("Week closed" / "Campaign ended" + expired), one rule
        from datetime import datetime, timezone
        from shared import campaign_status, campaigns
        rules = campaigns.get(c["campaign"]) if c["campaign"] else None
        cur.execute("SELECT posted_at FROM clip_posts WHERE candidate_id = %s AND user_id = %s", (candidate_id, user["id"]))
        posts = [{"posted_at": r[0]} for r in cur.fetchall()]
        state["campaign_labels"] = campaign_status.clip_labels(rules, posts, datetime.now(timezone.utc))
        return state


class HookTitleIn(BaseModel):
    on: bool = True
    text: str = ""
    duration: float = edit_specs.HOOK_TITLE_DEFAULT_DURATION


@editor.put("/hook-title")
def put_hook_title(job_id: str, candidate_id: str, body: HookTitleIn, user: dict = Depends(get_current_user)):
    try:
        value = edit_specs.normalize_hook_title(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
        if c["status"] in ("preview_queued", "preview_rendering", "render_queued", "rendering"):
            raise HTTPException(status_code=409, detail="This clip is rendering; try again when it's done")
        before = edit_specs.hook_title_of(c["edit_spec"]) or {}
        where, params = owner_filter(user)
        cur.execute(
            f"""
            UPDATE clip_candidates c SET edit_spec = COALESCE(c.edit_spec, '{{}}'::jsonb) || %s::jsonb,
                   updated_at = NOW()
            FROM jobs j
            WHERE c.id::text = %s AND c.job_id::text = %s AND j.id = c.job_id AND {where}
            """,
            [core.json_param({"hook_title": value}), candidate_id, job_id, *params],
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=404, detail="Clip not found")
        if value != before:
            core.mark_finals_outdated(cur, c["job_id"], candidate_id)  # 114: same transaction
        conn.commit()
        return _state(_load(cur, job_id, candidate_id, user))


@editor.get("/timeline")
def editor_timeline(job_id: str, candidate_id: str, user: dict = Depends(get_current_user)):
    """Cached timeline written by the worker after the last preview render; without one (older
    previews), word chips only (`peaks: null`) so the UI still seeks by word."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
        cur.execute("SELECT c.subtitle_segments, j.effective_language, j.language FROM clip_candidates c "
                    "JOIN jobs j ON j.id = c.job_id WHERE c.id::text = %s", (candidate_id,))
        segments, eff_lang, req_lang = cur.fetchone() or (None, None, None)
        segments = segments or []
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    cached = timelines.read_cache(timelines.cache_path(core.DATA_ROOT / "previews", candidate_id), c["preview_path"])
    data = {**cached, "cached": True} if cached and cached.get("words") else {**timelines.words_only(segments, duration), "cached": False}
    # 5b: filler-word SUGGESTIONS (never cut until the user accepts), computed per request so list
    # changes in shared/languages.py apply without re-rendering
    lang = languages.job_language(eff_lang, req_lang)
    data["fillers"] = languages.filler_spans(data["words"], lang)
    data["language"] = lang
    return data


class CutsIn(BaseModel):
    trim: list[float] | None = None
    removed: list[list[float]] = []


@editor.put("/cuts")
def put_cuts(job_id: str, candidate_id: str, body: CutsIn, user: dict = Depends(get_current_user)):
    """Trim window + removed ranges (clip-relative source seconds). Empty = no cuts (key removed)."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    try:
        value = edit_specs.normalize_cuts(body.model_dump(), duration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _save_spec_key(job_id, candidate_id, user, "cuts", value)


class ZoomIn(BaseModel):
    on: bool = True
    intensity: float = edit_specs.ZOOM_DEFAULT_INTENSITY
    markers: list[float] = []


@editor.put("/zoom")
def put_zoom(job_id: str, candidate_id: str, body: ZoomIn, user: dict = Depends(get_current_user)):
    """Punch-in markers (clip-relative source seconds) + on/intensity (P4 task 4/5)."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    try:
        value = edit_specs.normalize_zoom(body.model_dump(), duration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _save_spec_key(job_id, candidate_id, user, "zoom", value)


class ProgressIn(BaseModel):
    on: bool = False
    color: str = edit_specs.PROGRESS_COLORS[0]


@editor.put("/progress")
def put_progress(job_id: str, candidate_id: str, body: ProgressIn, user: dict = Depends(get_current_user)):
    """Progress bar overlay (P4 task 5)."""
    try:
        value = edit_specs.normalize_progress(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _save_spec_key(job_id, candidate_id, user, "progress", value)


class AudioIn(BaseModel):
    compress: bool = False
    loud: bool = False
    silence_trim: bool = False
    silence_ranges: list[list[float]] = []


@editor.put("/audio")
def put_audio(job_id: str, candidate_id: str, body: AudioIn, user: dict = Depends(get_current_user)):
    """Audio tab (P4 task 5): light compression + the Remove-silences toggle state. The pause cuts themselves
    live in edit_spec.cuts (PUT …/cuts); loudness is always on and not editable here."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    try:
        value = edit_specs.normalize_audio(body.model_dump(), duration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _save_spec_key(job_id, candidate_id, user, "audio", value)


class FixLengthIn(BaseModel):
    target: float


def _keep(cuts, clip):
    a, b = (cuts or {}).get("trim") or [0.0, clip]
    keep = [[float(a), float(b)]]
    for s, e in (cuts or {}).get("removed") or []:
        nxt = []
        for x, y in keep:
            if e <= x or s >= y:
                nxt.append([x, y])
            else:
                if s > x: nxt.append([x, s])
                if e < y: nxt.append([e, y])
        keep = nxt
    return keep


@editor.put("/fix-length")
def fix_length(job_id: str, candidate_id: str, body: FixLengthIn, user: dict = Depends(get_current_user)):
    """Review quick fix "Trim to N s": end the trim where the OUTPUT reaches N seconds (existing cuts kept)."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    clip = float(c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0)))
    target = float(body.target)
    if target < 1 or not clip:
        raise HTTPException(status_code=400, detail="target must be at least 1 second")
    cuts = edit_specs.cuts_of(c["edit_spec"] if isinstance(c["edit_spec"], dict) else None) or {}
    keep, acc, end = _keep(cuts, clip), 0.0, None
    for a, b in keep:
        if acc + (b - a) >= target:
            end = a + (target - acc)
            break
        acc += b - a
    if end is None:
        return _state(c)                                   # already short enough: nothing to do
    start = keep[0][0] if keep else 0.0
    value = edit_specs.normalize_cuts({"trim": [start, round(end, 3)], "removed": cuts.get("removed") or []}, clip)
    return _save_spec_key(job_id, candidate_id, user, "cuts", value)


# --------------------------------------------------------------------------- Review page (task 6 + filters)

review = APIRouter(prefix="/api/review", tags=["review"])
REVIEW_FILTER_KEY = "REVIEW_FILTER"        # per user, user_settings (not a settings-UI key)
REVIEW_STATUSES = {"to_review": ("review",), "approved": ("render_queued", "rendering", "completed"), "all": None}
READY_JOB_STATUSES = ("review", "completed", "partial_failure")


def _review_filter(raw) -> dict:
    import json
    try:
        f = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except ValueError:
        f = {}
    status = f.get("status") if f.get("status") in REVIEW_STATUSES else "to_review"
    return {"campaign": str(f.get("campaign") or "all")[:80], "job": str(f.get("job") or "all")[:80], "status": status}


@review.get("/filter")
def get_review_filter(user: dict = Depends(get_current_user)):
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT value FROM user_settings WHERE user_id = %s AND key = %s", (user["id"], REVIEW_FILTER_KEY))
        row = cur.fetchone()
    return _review_filter(row[0] if row else None)


class ReviewFilterIn(BaseModel):
    campaign: str = "all"
    job: str = "all"
    status: str = "to_review"


@review.put("/filter")
def put_review_filter(body: ReviewFilterIn, user: dict = Depends(get_current_user)):
    import json
    value = _review_filter(body.model_dump())
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        # QA 649ae25 Low 2: never store another user's job id or an unknown campaign (reads ignored them anyway)
        if value["job"] != "all":
            where, params = owner_filter(user)
            cur.execute(f"SELECT 1 FROM jobs j WHERE j.id::text = %s AND {where}", [value["job"], *params])
            if not cur.fetchone():
                value["job"] = "all"
        if value["campaign"] not in ("all", "none"):
            from shared import campaigns
            if not campaigns.get(value["campaign"]):
                value["campaign"] = "all"
        core.set_user_setting(cur, user["id"], REVIEW_FILTER_KEY, json.dumps(value))
        conn.commit()
    return value


@review.get("/clips")
def review_clips(campaign: str = "all", job: str = "all", status: str = "to_review",
                 user: dict = Depends(get_current_user)):
    """Clips for the Review page across the caller's jobs (owner-scoped), filtered by campaign
    ('all' | slug | 'none'), job ('all' | id) and status ('to_review' | 'approved' | 'all'); earnable clips
    first by hook score, then the ones that can no longer earn."""
    from datetime import datetime, timezone
    from shared import campaigns, payouts, rule_checks
    from shared import campaign_status as campaign_status_mod
    from shared.review_state import campaign_status
    core = _core()
    now = datetime.now(timezone.utc)
    where, params = owner_filter(user)
    conds = [where, "j.status = ANY(%s)"]
    params = [*params, list(READY_JOB_STATUSES)]
    if campaign == "none":
        conds.append("j.campaign IS NULL")
    elif campaign != "all":
        conds.append("j.campaign = %s"); params.append(campaign)
    if job != "all":
        conds.append("j.id::text = %s"); params.append(job)
    statuses = REVIEW_STATUSES.get(status, REVIEW_STATUSES["to_review"])
    if statuses:
        conds.append("c.status = ANY(%s)"); params.append(list(statuses))
    cols = ["id", "job_id", "clip_index", "status", "score", "title", "manual_title", "ai_title", "reason", "start_time",
            "end_time", "duration_seconds", "edit_spec", "description", "render_warnings", "safety_check", "updated_at"]
    with core.get_db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT {", ".join("c." + k for k in cols)}, j.campaign, coalesce(j.custom_title, s.title), j.created_at, j.status
                FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
                LEFT JOIN source_videos s ON s.id = j.source_video_id
                WHERE {" AND ".join(conds)}""", params)
        rows = cur.fetchall()
        ids = [r[0] for r in rows]
        posts = {}
        if ids:
            cur.execute("SELECT candidate_id, platform, status, posted_at FROM clip_posts WHERE candidate_id = ANY(%s) "
                        "AND user_id = %s", (ids, user["id"]))
            for cid, plat, st, at in cur.fetchall():
                posts.setdefault(cid, []).append({"platform": plat, "status": st, "posted_at": at})
    rules_cache, clips = {}, []
    for r in rows:
        c = dict(zip(cols, r))
        slug, jtitle, jdate, jstatus = r[len(cols):]
        if slug not in rules_cache:
            rules = campaigns.get(slug) if slug else None
            rules_cache[slug] = (rules, payouts.model_from_rules(rules) if rules else None)
        rules, model = rules_cache[slug]
        c["rule_checks"] = rule_checks.check(rules, c) if rules else []
        c.update(campaign_status_mod.clip_labels(rules, posts.get(c["id"], []), now))   # 162: earn + expired
        c.update(campaign=slug, job_title=jtitle or "Untitled video", job_date=jdate.isoformat() if jdate else None,
                 job_status=jstatus, updated_at=c["updated_at"].isoformat() if c["updated_at"] else None,
                 score=float(c["score"]) if c["score"] is not None else None)
        for k in ("start_time", "end_time", "duration_seconds"):
            c[k] = float(c[k]) if c[k] is not None else None
        for k in ("description", "safety_check", "render_warnings"):
            c.pop(k, None)
        clips.append(c)
    clips.sort(key=lambda c: (c["earn"] is not None, -(c["score"] if c["score"] is not None else -1), c["clip_index"] or 0))
    to_review = sum(1 for c in clips if c["status"] == "review")
    if job != "all":
        jt = clips[0]["job_title"] if clips else None
        header = {"kind": "job", "title": jt, "job": job}
    elif campaign not in ("all", "none"):
        rules = campaigns.get(campaign)
        header = {"kind": "campaign", "title": campaigns.display_name(rules) if rules else campaign, "campaign": campaign,
                  **({"status": campaign_status(rules, now)} if rules else {})}
    else:
        header = {"kind": campaign, "title": "Clips without a campaign" if campaign == "none" else "All clips"}
    return {"header": {**header, "to_review": to_review}, "clips": clips,
            "filter": {"campaign": campaign, "job": job, "status": status if status in REVIEW_STATUSES else "to_review"}}


def environment():
    """Open (no auth, no secrets): which stack this is, for the STAGING banner on every screen."""
    return {"env": os.getenv("CLIPFLOW_ENV") or "production"}


# --------------------------------------------------------------------------- Auto Edit E1: edit plan

def _plan_inputs(c: dict, user: dict):
    """Words/peaks/frames from the preview's timeline cache + this clip's cuts and hook card window."""
    core = _core()
    spec = c["edit_spec"] if isinstance(c["edit_spec"], dict) else {}
    duration = float(c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0)) or 0)
    previews = core.DATA_ROOT / "previews"
    cached = timelines.read_cache(timelines.cache_path(previews, c["id"]), c["preview_path"]) or {}
    cuts = edit_specs.cuts_of(spec) or {}
    trim = cuts.get("trim")
    removed = cuts.get("removed") or []
    ht = edit_specs.hook_title_of(spec) or {}
    card = float(ht.get("duration") or edit_specs.HOOK_TITLE_DEFAULT_DURATION) if ht.get("on") else 0.0
    frames = []
    vision_on = str(core.runtime_setting("EDIT_DIRECTOR_VISION", user_id=user["id"]) or "true").lower() not in (
        "false", "0", "no", "off")
    if vision_on:
        for f in (cached.get("frames") or [])[: edit_director.FRAME_COUNT]:
            path = previews / str(f.get("file", ""))
            if path.parent == previews and path.name.startswith(c["id"]) and path.is_file():
                try:
                    frames.append((float(f["t"]), path.read_bytes()))
                except (OSError, KeyError, TypeError, ValueError):
                    pass
    return duration, cached, removed, trim, card, frames


@editor.post("/plan")
def generate_plan(job_id: str, candidate_id: str, user: dict = Depends(get_current_user)):
    """Generate / regenerate the edit plan (one utility-AI call, + frames when available). Replaces the plan."""
    from datetime import datetime, timezone
    from shared.ai import router as ai_router
    from shared.errors import AIError, AINotConfiguredError
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    duration, cached, removed, trim, card, frames = _plan_inputs(c, user)
    if duration <= 0:
        raise HTTPException(status_code=409, detail="This clip has no duration yet")
    words = cached.get("words") or []
    if not words:
        raise HTTPException(status_code=409, detail="Render a preview first: the plan reads its transcript and audio")
    prompt = edit_director.moments_prompt(words, duration, frame_times=[t for t, _ in frames],
                                          title=(c["manual_title"] or c["title"] or c["ai_title"] or ""))
    try:
        data, meta = ai_router.ai_generate_json(prompt, edit_director.MOMENTS_SCHEMA, task="edit_moments",
                                                max_tokens=1200, attempts=1, with_meta=True,
                                                images=[b for _, b in frames] or None)
    except AINotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        if not frames:
            raise HTTPException(status_code=502, detail=f"The AI couldn't plan this clip: {str(exc)[:200]}")
        print(f"[backend] edit plan: vision call failed ({type(exc).__name__}), retrying text-only")
        frames = []
        prompt = edit_director.moments_prompt(words, duration, title=(c["manual_title"] or c["title"] or ""))
        try:
            data, meta = ai_router.ai_generate_json(prompt, edit_director.MOMENTS_SCHEMA, task="edit_moments",
                                                    max_tokens=1200, attempts=1, with_meta=True)
        except AIError as exc2:
            raise HTTPException(status_code=502, detail=f"The AI couldn't plan this clip: {str(exc2)[:200]}")
    moments = edit_director.parse_moments(data, duration)
    spec = c["edit_spec"] if isinstance(c["edit_spec"], dict) else {}
    z = edit_specs.zoom_of(spec) or {}
    items = edit_director.plan(            # restraint in OUTPUT seconds; the user's zoom markers count (QA a156a53)
        duration=duration, moments=moments,
        loud=edit_director.loudness_peaks(cached.get("peaks"), float(cached.get("rate") or 0)),
        cuts=edit_director.cut_points(removed), card_seconds=card, removed=removed, trim=trim,
        keep=_keep({"trim": trim, "removed": removed}, duration) if (trim or removed) else None,
        taken=(z.get("markers") or []) if z.get("on", True) else [])
    value = edit_specs.normalize_director({
        "version": edit_director.VERSION, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": meta.get("provider"), "vision": bool(frames), "items": items}, duration)
    return _save_spec_key(job_id, candidate_id, user, "director", value)


class PlanIn(BaseModel):
    items: list[dict] = []


@editor.put("/plan")
def put_plan(job_id: str, candidate_id: str, body: PlanIn, user: dict = Depends(get_current_user)):
    """Update plan items by id (items not sent are kept), add user items (t + effect); empty items = clear."""
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, job_id, candidate_id, user)
    spec = c["edit_spec"] if isinstance(c["edit_spec"], dict) else {}
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    current = edit_specs.director_of(spec) or {}
    if not body.items:
        return _save_spec_key(job_id, candidate_id, user, "director", None)
    by_id = {i["id"]: i for i in current.get("items") or []}
    added = []
    for it in body.items:            # by id: {id, on} updates that item, items not sent stay; new ones need t + effect
        if not isinstance(it, dict):
            raise HTTPException(status_code=400, detail="plan items must be objects")
        if it.get("id") in by_id:
            by_id[it["id"]] = {**by_id[it["id"]], **it}
        elif "t" in it and "effect" in it:
            added.append({**it, "source": "user"})
        else:
            raise HTTPException(status_code=400, detail=f"Unknown plan item {str(it.get('id'))[:40]!r}")
    merged = list(by_id.values()) + added
    try:
        value = edit_specs.normalize_director({**current, "items": merged}, duration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _save_spec_key(job_id, candidate_id, user, "director", value)


router.include_router(editor)
router.include_router(review)
router.add_api_route("/api/env", environment, methods=["GET"], tags=["meta"])

