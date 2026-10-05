"""Editor API (lane B, roadmap P4). Mounted by one line in main.py (`# lane-b hook`).

Every endpoint takes the current user through ONE dependency, `get_current_user`, and scopes its
queries to the candidate's job owner (`owner_filter`). Until Lane A's accounts (P1.5) land, the
placeholder returns the admin and jobs have no owner column, so the filter is a no-op; when
`jobs.owner_id` exists, non-admins only see their own jobs automatically. Nothing is stored outside
the owned job/candidate rows (all editor state lives in clip_candidates.edit_spec).

main.py is imported lazily (inside handlers) to avoid a circular import; its helpers keep one
implementation of the DB connection, json params and the 114 "final outdated" marking.

Routes (all under /api, so the API-key middleware applies):
  GET /api/editor/candidates/{cid}              editor state for one clip
  PUT /api/editor/candidates/{cid}/hook-title   {on, text, duration} → edit_spec.hook_title
Rendering stays on the existing POST /api/jobs/{jid}/candidates/{cid}/regenerate-preview (island
progress via /api/activity, version history).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shared import edit_spec as edit_specs

router = APIRouter(prefix="/api/editor", tags=["editor"])


# --------------------------------------------------------------------------- current user + owner scope

class CurrentUser(BaseModel):
    id: Optional[str] = None
    name: str = "admin"
    is_admin: bool = True


def get_current_user() -> CurrentUser:
    """PLACEHOLDER until Lane A's accounts (P1.5): everyone is the admin. Lane A replaces the body
    (or overrides it with app.dependency_overrides[get_current_user]); the signature stays."""
    return CurrentUser()


_owner_col: Optional[bool] = None


def _has_owner_column(cur) -> bool:
    global _owner_col
    if _owner_col is None:
        cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'jobs' AND column_name = 'owner_id'")
        _owner_col = cur.fetchone() is not None
    return _owner_col


def owner_filter(cur, user: CurrentUser, alias: str = "j") -> tuple[str, list]:
    """SQL fragment + params limiting rows to jobs this user owns (admins: all)."""
    if user.is_admin or not _has_owner_column(cur):
        return "TRUE", []
    if not user.id:
        return "FALSE", []
    return f"{alias}.owner_id::text = %s", [str(user.id)]


def _core():
    from app import main as core  # lazy: main imports this module
    return core


def _load(cur, cid: str, user: CurrentUser) -> dict:
    """Candidate + its job, owner-scoped. 404 when missing or not this user's (no existence leak)."""
    where, params = owner_filter(cur, user)
    cur.execute(
        f"""
        SELECT c.id::text, c.job_id::text, c.status, c.title, c.manual_title, c.ai_title, c.reason,
               c.start_time, c.end_time, c.duration_seconds, c.edit_spec, c.preview_path, c.final_path,
               c.updated_at, s.title, j.custom_title, j.platform, j.campaign, j.status
        FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
        LEFT JOIN source_videos s ON s.id = j.source_video_id
        WHERE c.id::text = %s AND {where}
        """,
        [cid, *params],
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
            "updated_at": c["updated_at"].isoformat() if c["updated_at"] else None,
            "edit_spec": spec,
        },
        "hook_title": {
            "on": bool(ht.get("on", False)), "text": ht.get("text", ""),
            "duration": ht.get("duration", edit_specs.HOOK_TITLE_DEFAULT_DURATION),
            "default_text": default_text, "durations": list(edit_specs.HOOK_TITLE_DURATIONS),
            "max_chars": edit_specs.HOOK_TITLE_MAX_CHARS,
        },
    }


# --------------------------------------------------------------------------- routes

@router.get("/candidates/{candidate_id}")
def editor_state(candidate_id: str, user: CurrentUser = Depends(get_current_user)):
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        return _state(_load(cur, candidate_id, user))


class HookTitleIn(BaseModel):
    on: bool = True
    text: str = ""
    duration: float = edit_specs.HOOK_TITLE_DEFAULT_DURATION


@router.put("/candidates/{candidate_id}/hook-title")
def put_hook_title(candidate_id: str, body: HookTitleIn, user: CurrentUser = Depends(get_current_user)):
    try:
        value = edit_specs.normalize_hook_title(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    core = _core()
    with core.get_db() as conn, conn.cursor() as cur:
        c = _load(cur, candidate_id, user)
        if c["status"] in ("preview_queued", "preview_rendering", "render_queued", "rendering"):
            raise HTTPException(status_code=409, detail="This clip is rendering; try again when it's done")
        before = edit_specs.hook_title_of(c["edit_spec"]) or {}
        where, params = owner_filter(cur, user)
        cur.execute(
            f"""
            UPDATE clip_candidates c SET edit_spec = COALESCE(c.edit_spec, '{{}}'::jsonb) || %s::jsonb,
                   updated_at = NOW()
            FROM jobs j
            WHERE c.id::text = %s AND j.id = c.job_id AND {where}
            """,
            [core.json_param({"hook_title": value}), candidate_id, *params],
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=404, detail="Clip not found")
        if value != before:
            core.mark_finals_outdated(cur, c["job_id"], candidate_id)  # 114: same transaction
        conn.commit()
        return _state(_load(cur, candidate_id, user))
