"""Editor API (lane B, roadmap P4). Mounted by one line in main.py (`# lane-b hook`).

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
Rendering stays on the existing POST /api/jobs/{jid}/candidates/{cid}/regenerate-preview (island
progress via /api/activity, version history).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shared import edit_spec as edit_specs
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
               c.updated_at, s.title, j.custom_title, j.platform, j.campaign, j.status
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
            "job_custom_title", "platform", "campaign", "job_status"]
    return dict(zip(keys, row))


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
        "hook_title": {
            "on": bool(ht.get("on", False)), "text": ht.get("text", ""),
            "duration": ht.get("duration", edit_specs.HOOK_TITLE_DEFAULT_DURATION),
            "default_text": default_text, "durations": list(edit_specs.HOOK_TITLE_DURATIONS),
            "max_chars": edit_specs.HOOK_TITLE_MAX_CHARS,
        },
    }


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
        return _state(_load(cur, job_id, candidate_id, user))


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
        cur.execute("SELECT subtitle_segments FROM clip_candidates WHERE id::text = %s", (candidate_id,))
        segments = (cur.fetchone() or [None])[0] or []
    duration = c["duration_seconds"] or ((c["end_time"] or 0) - (c["start_time"] or 0))
    cached = timelines.read_cache(timelines.cache_path(core.DATA_ROOT / "previews", candidate_id), c["preview_path"])
    if cached and cached.get("words"):
        return {**cached, "cached": True}
    return {**timelines.words_only(segments, duration), "cached": False}


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


def environment():
    """Open (no auth, no secrets): which stack this is, for the STAGING banner on every screen."""
    return {"env": os.getenv("CLIPFLOW_ENV") or "production"}


router.include_router(editor)
router.add_api_route("/api/env", environment, methods=["GET"], tags=["meta"])
