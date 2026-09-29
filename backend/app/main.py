import hashlib
import hmac
import json
import os
import re
import secrets
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from shared.ai import router as ai_router
from shared.errors import AINotConfiguredError
from shared.settings import (
    DEFAULT_SETTINGS,
    SECRET_SETTING_KEYS,
    RuntimeSettings,
)


# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.environ["DATABASE_URL"]

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/data"))


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Riftstorm Clip Pipeline",
    version="4.0",
)


# ============================================================
# AUTH (R-03) — shared secret in X-ClipFlow-Key on every /api/*
# request. /health and / stay open. The expected value is env-only
# (CLIPFLOW_API_KEY), never app_settings: that table is served over
# the API. Enforced as middleware rather than a route dependency so
# unknown /api paths also get 401 (no route-existence leak).
#
# <img>/<video>/download links can't send headers, so the GET file
# routes in MEDIA_PATH_RE also accept ?mt=<exp>.<hmac>, a read-only
# media token from GET /api/media-token, HMAC'd with the API key.
# Tokens are bucketed to MEDIA_TOKEN_WINDOW so media URLs stay stable
# for hours (re-renders don't reload playing videos); every token is
# valid for 12-24 h. Rotating CLIPFLOW_API_KEY revokes all of them.
# ============================================================

API_KEY_HEADER = "X-ClipFlow-Key"

CLIPFLOW_API_KEY = os.getenv("CLIPFLOW_API_KEY", "").strip()

MEDIA_TOKEN_PARAM = "mt"

MEDIA_TOKEN_WINDOW = 12 * 3600

MEDIA_PATH_RE = re.compile(
    r"^/api/("
    r"jobs/[^/]+/candidates/[^/]+/"
    r"(preview|render|thumbnail|thumbnail-options/\d+)"
    r"|assets/watermarks/[^/]+/file"
    r")$"
)

if not CLIPFLOW_API_KEY:
    print(
        "[backend] CLIPFLOW_API_KEY is not set: every /api/* "
        "request will be rejected with 401 (fail closed)."
    )


def _media_signature(exp: int) -> str:
    return hmac.new(
        CLIPFLOW_API_KEY.encode(),
        f"media:{exp}".encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_media_token() -> dict:
    exp = (
        int(time.time()) // MEDIA_TOKEN_WINDOW + 2
    ) * MEDIA_TOKEN_WINDOW
    return {
        "token": f"{exp}.{_media_signature(exp)}",
        "expires_at": exp,
    }


def _media_token_valid(token: str) -> bool:
    exp_raw, _, sig = token.partition(".")
    try:
        exp = int(exp_raw)
    except ValueError:
        return False
    if exp <= time.time():
        return False
    return secrets.compare_digest(sig, _media_signature(exp))


def _request_authorized(request: Request) -> bool:
    if not CLIPFLOW_API_KEY:
        return False

    supplied = request.headers.get(API_KEY_HEADER, "")
    if supplied and secrets.compare_digest(
        supplied.encode(), CLIPFLOW_API_KEY.encode()
    ):
        return True

    token = request.query_params.get(MEDIA_TOKEN_PARAM, "")
    return bool(
        token
        and request.method in ("GET", "HEAD")
        and MEDIA_PATH_RE.match(request.url.path)
        and _media_token_valid(token)
    )


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    if (
        (path == "/api" or path.startswith("/api/"))
        and not _request_authorized(request)
    ):
        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
        )
    return await call_next(request)


# CORS: explicit origin list from env CORS_ALLOWED_ORIGINS (comma
# separated), never "*". No credentials: auth is a header, not a
# cookie. Added AFTER the auth middleware so it wraps it: preflights
# are answered here and 401s still carry CORS headers.
def cors_allowed_origins() -> list[str]:
    origins = [
        o.strip().rstrip("/")
        for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    if "*" in origins:
        print("[backend] CORS_ALLOWED_ORIGINS: '*' ignored")
        origins = [o for o in origins if o != "*"]
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", API_KEY_HEADER],
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return psycopg.connect(DATABASE_URL)


@app.on_event("startup")
def ensure_schema():
    """
    Lightweight, idempotent migration, run on every boot. Each
    statement commits on its own — one statement failing (a bad type,
    a permissions issue, whatever) must never silently roll back the
    others, since they previously all shared one transaction and one
    commit at the end. That was a real bug: a single failing CREATE
    TABLE further down this list could abort the whole transaction
    and make an earlier, perfectly valid ALTER TABLE ADD COLUMN look
    like it never ran.
    """
    statements = [
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS custom_title TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS description TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS thumbnail_options JSONB",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS subtitle_animation TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS thumbnail_locked BOOLEAN DEFAULT FALSE",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS submagic_project_id TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS submagic_status TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS submagic_preview_url TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS submagic_download_url TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS submagic_error TEXT",
        """
        CREATE TABLE IF NOT EXISTS candidate_versions (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            version INT NOT NULL,
            label TEXT NOT NULL,
            snapshot JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_candidate_versions_candidate
        ON candidate_versions (candidate_id, version DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS watermark_assets (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            width INT,
            height INT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        # R-22: which AI provider produced this candidate's hook.
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS hook_provider TEXT",
    ]

    try:
        with get_db() as conn:
            for stmt in statements:
                try:
                    with conn.cursor() as cur:
                        cur.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    print(
                        "[backend] ensure_schema statement failed:\n"
                        + stmt.strip()
                        + "\n"
                        + traceback.format_exc()
                    )
    except Exception:
        print(
            "[backend] ensure_schema fatal error:",
            traceback.format_exc(),
        )


# ============================================================
# HELPERS
# ============================================================

DEFAULT_SUBTITLE_STYLE = {
    "style": "outline",
    "font": "Liberation Sans Bold",
    "size": 42,
    "bold": True,
    "color": "white",
    "outline": 5,
    "position": "bottom",
    "animation": "karaoke",
}

# Keep this in sync with the ANIMATIONS catalog in worker.py's make_ass().
SUBTITLE_ANIMATIONS = {
    "karaoke",
    "word_pop",
    "bounce",
    "typewriter",
    "fade_settle",
    "none",
}


def normalize_subtitle_style(
    value: Any = None,
    font: Optional[str] = None,
    size: Optional[int] = None,
    animation: Optional[str] = None,
) -> dict:

    style = DEFAULT_SUBTITLE_STYLE.copy()

    if isinstance(value, dict):
        style.update(value)

    elif isinstance(value, str):

        value_lower = value.strip().lower()

        # Compatibility with old frontend values
        if value_lower == "bold":
            style["bold"] = True

        elif value_lower == "normal":
            style["bold"] = False

        elif value_lower:
            # Treat a plain string as font name,
            # not JSON.
            style["font"] = value.strip()

    if font:
        style["font"] = font

    if size:
        style["size"] = int(size)

    if animation:
        style["animation"] = animation

    style["animation"] = str(
        style.get("animation", "karaoke")
    ).strip().lower() or "karaoke"

    if style["animation"] not in SUBTITLE_ANIMATIONS:
        style["animation"] = "karaoke"

    # Sanitize fields
    style["font"] = str(
        style.get("font", "Liberation Sans Bold")
    )

    try:
        style["size"] = int(style.get("size", 42))
    except Exception:
        style["size"] = 42

    style["bold"] = bool(
        style.get("bold", True)
    )

    style["color"] = str(
        style.get("color", "white")
    )

    try:
        style["outline"] = int(
            style.get("outline", 3)
        )
    except Exception:
        style["outline"] = 3

    style["position"] = str(
        style.get("position", "bottom")
    )

    return style


def json_param(value: Any) -> str:
    """
    Convert Python dict/list/etc to valid JSON text.
    PostgreSQL JSONB accepts this safely.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
    )


def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# MODELS
# ============================================================

class ClipRequest(BaseModel):
    youtube_url: str

    custom_title: Optional[str] = None

    layout: str = "auto"

    platform: str = "youtube_shorts"

    split_ratio: float = Field(
        default=70.0,
        ge=60.0,
        le=70.0,
    )

    subtitle_style: Any = None

    subtitle_font: str = "Liberation Sans Bold"

    subtitle_size: int = Field(
        default=42,
        ge=12,
        le=120,
    )

    subtitle_animation: str = "karaoke"


class CandidateUpdate(BaseModel):
    title: Optional[str] = None

    manual_title: Optional[str] = None

    subtitle_text: Optional[str] = None

    subtitle_override: Optional[str] = None

    start_seconds: Optional[float] = None

    end_seconds: Optional[float] = None

    content_type: Optional[str] = None

    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
    )

    description: Optional[str] = None

    selected_thumbnail_index: Optional[int] = None


class JobUpdate(BaseModel):
    custom_title: Optional[str] = None


class SubtitleStyleUpdate(BaseModel):
    subtitle_style: Any = None

    subtitle_font: Optional[str] = None

    subtitle_size: Optional[int] = None

    subtitle_animation: Optional[str] = None


CONTENT_TYPES = [
    "Funny",
    "Wise",
    "Reality",
    "Hype",
    "Wholesome",
    "Educational",
]

SUPPORTED_PLATFORMS = {
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
}

# "auto" lets the worker pick whichever corner scores highest (today's
# behavior). "left"/"right" hint the worker to bias face detection
# toward a facecam it already knows sits on that side, and to fall
# back to that side if no face is detected at all.
SUPPORTED_LAYOUTS = {
    "auto",
    "left",
    "right",
}

# DEFAULT_SETTINGS (whitelist + defaults) and SECRET_SETTING_KEYS live
# in shared/settings.py so backend and worker agree on both.

class SettingsUpdate(BaseModel):
    values: dict[str, str]

# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "service": "riftstorm-backend",
        "version": "3.0",
        "status": "ok",
    }


@app.get("/health")
def health():

    try:

        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    "SELECT 1"
                )

                cur.fetchone()

        return {
            "status": "healthy"
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/media-token")
def media_token():
    """Read-only token for <img>/<video> src URLs (see AUTH above)."""
    return issue_media_token()


# ============================================================
# CREATE JOB
# ============================================================

@app.post("/api/jobs")
def create_job(req: ClipRequest):

    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail="platform must be youtube_shorts, tiktok, or instagram_reels",
        )

    if req.layout not in SUPPORTED_LAYOUTS:
        raise HTTPException(
            status_code=400,
            detail="layout must be auto, left, or right",
        )

    # DEFAULT_SUBTITLE_* settings apply only to fields the client
    # didn't send (the Import form omits them on purpose).
    sent = req.model_fields_set

    style = normalize_subtitle_style(
        req.subtitle_style
        if "subtitle_style" in sent
        else {"style": runtime_setting("DEFAULT_SUBTITLE_STYLE")},
        req.subtitle_font
        if "subtitle_font" in sent
        else runtime_setting("DEFAULT_SUBTITLE_FONT"),
        req.subtitle_size
        if "subtitle_size" in sent
        else _settings.get_int("DEFAULT_SUBTITLE_SIZE"),
        req.subtitle_animation,
    )

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                # ------------------------------------------------
                # SOURCE VIDEO
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO source_videos (
                        youtube_url
                    )
                    VALUES (%s)
                    ON CONFLICT (youtube_url)
                    DO UPDATE SET
                        youtube_url = EXCLUDED.youtube_url
                    RETURNING id
                    """,
                    (
                        req.youtube_url,
                    ),
                )

                source_video_id = cur.fetchone()[0]

                # ------------------------------------------------
                # JOB
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO jobs (
                        source_video_id,
                        custom_title,
                        job_type,
                        status,
                        progress,
                        message,
                        layout,
                        platform,
                        split_ratio,
                        subtitle_style,
                        subtitle_font,
                        subtitle_size,
                        subtitle_animation
                    )
                    VALUES (
                        %s,
                        %s,
                        'clip_pipeline',
                        'queued',
                        0,
                        'Waiting for worker',
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        source_video_id,
                        (req.custom_title or "").strip() or None,
                        req.layout,
                        req.platform,
                        req.split_ratio,
                        json_param(style),
                        style["font"],
                        style["size"],
                        style["animation"],
                    ),
                )

                job_id = cur.fetchone()[0]

            conn.commit()

        return {
            "id": str(job_id),
            "job_id": str(job_id),
            "status": "queued",
            "subtitle_style": style,
        }

    except Exception as exc:

        print(
            "[backend] create_job error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# LIST JOBS
# ============================================================

@app.get("/api/jobs")
def list_jobs(
    scope: str = "current",
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                if scope == "previous":

                    status_filter = """
                        j.status IN (
                            'completed',
                            'failed',
                            'cancelled'
                        )
                    """

                elif scope == "queue":

                    # Clip Queue / Job History includes paused jobs and all
                    # finished/terminal/review jobs. Active processing jobs
                    # stay in the Editing Panel only.
                    status_filter = """
                        j.status IN (
                            'paused',
                            'completed',
                            'failed',
                            'cancelled',
                            'review'
                        )
                    """

                else:

                    # Once a job's clips are ready ("review"), it should
                    # live only in the Clip Queue, not linger in the
                    # Editing Panel's active-jobs list too.
                    status_filter = """
                        j.status NOT IN (
                            'completed',
                            'failed',
                            'cancelled',
                            'paused',
                            'review'
                        )
                    """

                query = f"""
                    SELECT
                        j.id,
                        j.source_video_id,
                        sv.youtube_url,
                        sv.title AS source_title,
                        j.custom_title,
                        j.job_type,
                        j.status,
                        j.progress,
                        j.message,
                        j.error_stage,
                        j.error_message,
                        j.created_at,
                        j.started_at,
                        j.completed_at,
                        j.review_ready_at,
                        j.layout,
                        j.platform,
                        j.split_ratio,
                        j.subtitle_style,
                        j.subtitle_font,
                        j.subtitle_size,
                        j.subtitle_animation
                    FROM jobs j
                    LEFT JOIN source_videos sv
                        ON sv.id = j.source_video_id
                    WHERE {status_filter}
                    ORDER BY j.created_at DESC
                    """

                cur.execute(query)

                rows = cur.fetchall()

                columns = [
                    desc.name
                    for desc in cur.description
                ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    except Exception as exc:

        print(
            "[backend] list_jobs error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# GET JOB
# ============================================================

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        j.id,
                        j.source_video_id,
                        sv.youtube_url,
                        sv.title AS source_title,
                        j.custom_title,
                        j.job_type,
                        j.status,
                        j.progress,
                        j.message,
                        j.error_stage,
                        j.error_message,
                        j.created_at,
                        j.started_at,
                        j.completed_at,
                        j.review_ready_at,
                        j.layout,
                        j.platform,
                        j.split_ratio,
                        j.subtitle_style,
                        j.subtitle_font,
                        j.subtitle_size,
                        j.subtitle_animation
                    FROM jobs j
                    LEFT JOIN source_videos sv
                        ON sv.id = j.source_video_id
                    WHERE j.id = %s
                    """,
                    (job_id,),
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

                columns = [
                    desc.name
                    for desc in cur.description
                ]

                job = dict(
                    zip(columns, row)
                )

                # --------------------------------------------
                # Candidates
                # --------------------------------------------

                cur.execute(
                    """
                    SELECT
                        c.*
                    FROM clip_candidates c
                    WHERE c.job_id = %s
                    ORDER BY c.score DESC NULLS LAST,
                             c.created_at ASC
                    """,
                    (job_id,),
                )

                candidate_rows = cur.fetchall()

                candidate_columns = [
                    desc.name
                    for desc in cur.description
                ]

                job["candidates"] = [
                    dict(
                        zip(
                            candidate_columns,
                            candidate_row,
                        )
                    )
                    for candidate_row in candidate_rows
                ]

        return job

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] get_job error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# RENAME JOB (manual / campaign name)
# ============================================================

@app.patch("/api/jobs/{job_id}")
def update_job(job_id: str, req: JobUpdate):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE jobs
                    SET custom_title = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        (req.custom_title or "").strip() or None,
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

            conn.commit()

        return {"ok": True}

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] update_job error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# CANDIDATES
# ============================================================

@app.get("/api/jobs/{job_id}/candidates")
def get_candidates(job_id: str):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        *
                    FROM clip_candidates
                    WHERE job_id = %s
                    ORDER BY score DESC NULLS LAST,
                             created_at ASC
                    """,
                    (job_id,),
                )

                rows = cur.fetchall()

                columns = [
                    desc.name
                    for desc in cur.description
                ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# UPDATE CANDIDATE
# ============================================================

@app.patch(
    "/api/jobs/{job_id}/candidates/{candidate_id}"
)
def update_candidate(
    job_id: str,
    candidate_id: str,
    req: CandidateUpdate,
):

    try:

        fields = []
        values = []

        if req.title is not None:

            fields.append(
                "title = %s"
            )

            values.append(
                req.title
            )

        if req.manual_title is not None:

            fields.append(
                "manual_title = %s"
            )

            values.append(
                req.manual_title
            )

        if req.subtitle_text is not None:

            fields.append(
                "subtitle_text = %s"
            )

            values.append(
                req.subtitle_text
            )

        if req.subtitle_override is not None:

            fields.append(
                "subtitle_override = %s"
            )

            values.append(
                req.subtitle_override
            )

        if req.content_type is not None:
            if req.content_type not in CONTENT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid content_type",
                )
            fields.append("content_type = %s")
            values.append(req.content_type)

        if req.rating is not None:
            fields.append("rating = %s")
            values.append(req.rating)

        if req.description is not None:
            fields.append("description = %s")
            values.append(req.description)

        # Worker uses start_time/end_time; keep those columns in sync
        # when older API clients send start_seconds/end_seconds.
        if req.start_seconds is not None:
            fields.append("start_time = %s")
            values.append(req.start_seconds)

        if req.end_seconds is not None:
            fields.append("end_time = %s")
            values.append(req.end_seconds)

        if req.selected_thumbnail_index is not None:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT thumbnail_options
                        FROM clip_candidates
                        WHERE id = %s AND job_id = %s
                        """,
                        (candidate_id, job_id),
                    )
                    trow = cur.fetchone()

            options = (trow[0] if trow else None) or []
            idx = req.selected_thumbnail_index

            if not isinstance(options, list) or idx < 0 or idx >= len(options):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid selected_thumbnail_index",
                )

            fields.append("thumbnail_path = %s")
            values.append(options[idx])

            # Picking a thumbnail (AI-generated or manually uploaded)
            # "locks" it so a subsequent preview/final render doesn't
            # silently clobber the choice with a freshly extracted
            # frame — see create_preview()/render_final_candidate()
            # in worker.py.
            fields.append("thumbnail_locked = %s")
            values.append(True)

        if not fields:

            raise HTTPException(
                status_code=400,
                detail="Nothing to update",
            )

        values.extend([
            candidate_id,
            job_id,
        ])

        query = f"""
            UPDATE clip_candidates
            SET
                {", ".join(fields)},
                updated_at = NOW()
            WHERE id = %s
              AND job_id = %s
            RETURNING id
        """

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    query,
                    values,
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {
            "status": "updated",
            "candidate_id": candidate_id,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# UPDATE SUBTITLE STYLE
# ============================================================

@app.patch(
    "/api/jobs/{job_id}/subtitle-style"
)
def update_subtitle_style(
    job_id: str,
    req: SubtitleStyleUpdate,
):

    style = normalize_subtitle_style(
        req.subtitle_style,
        req.subtitle_font,
        req.subtitle_size,
        req.subtitle_animation,
    )

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE jobs
                    SET
                        subtitle_style = %s::jsonb,
                        subtitle_font = %s,
                        subtitle_size = %s,
                        subtitle_animation = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        json_param(style),
                        style["font"],
                        style["size"],
                        style["animation"],
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

            conn.commit()

        return {
            "status": "updated",
            "subtitle_style": style,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# REGENERATE PREVIEW (apply edits: title, subtitle override,
# job-level subtitle style, then re-render the preview)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/regenerate-preview"
)
def regenerate_preview(
    job_id: str,
    candidate_id: str,
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET status = 'preview_queued',
                        progress = 0,
                        message = 'Queued: regenerating preview with edits',
                        error_stage = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

                record_candidate_version(
                    cur, candidate_id, "Applied changes"
                )

            conn.commit()

        return {
            "status": "queued",
            "candidate_id": candidate_id,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# APPROVE CANDIDATE (trigger final, full-resolution render)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/approve"
)
def approve_candidate(
    job_id: str,
    candidate_id: str,
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET status = 'render_queued',
                        progress = 0,
                        message = 'Queued: rendering final approved clip',
                        error_stage = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

                record_candidate_version(
                    cur, candidate_id, "Final render requested"
                )

            conn.commit()

        return {
            "status": "queued",
            "candidate_id": candidate_id,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# RUNTIME SETTINGS
# ============================================================

def _load_app_settings() -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings")
            return {row[0]: row[1] for row in cur.fetchall()}


_settings = RuntimeSettings(
    _load_app_settings,
    log=lambda msg: print("[backend]", msg),
)


def runtime_setting(
    key: str,
    fallback: str | None = None,
) -> str | None:
    """
    Same rule as the worker's setting(): app_settings (DB) wins,
    then env, then fallback / DEFAULT_SETTINGS. 5 s cache; PUT
    /api/settings invalidates it. Env-only keys (CLIPFLOW_API_KEY)
    never come from the DB.
    """
    return _settings.get(key, fallback)


# Every AI call goes through shared/ai/router.py (R-20).
ai_router.configure(runtime_setting, lambda msg: print("[backend]", msg))


# ============================================================
# NEW HOOK (ask Gemini to pick a different moment for this
# candidate, avoiding time ranges already used by sibling
# candidates on the same job, then re-render its preview)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/new-hook"
)
def new_hook(
    job_id: str,
    candidate_id: str,
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT transcript_segments
                    FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )

                job_row = cur.fetchone()

                if not job_row:

                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

                segments = job_row[0] or []

                cur.execute(
                    """
                    SELECT
                        id,
                        start_time,
                        end_time
                    FROM clip_candidates
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )

                existing_ranges = cur.fetchall()

        if not segments:

            raise HTTPException(
                status_code=409,
                detail="No transcript available for this job",
            )

        transcript_with_times = "\n".join(
            f"[{seg.get('start', 0):.1f}-{seg.get('end', 0):.1f}] "
            f"{seg.get('text', '')}"
            for seg in segments
        )[:15000]

        avoid_ranges = "\n".join(
            f"- {float(r[1]):.1f}s to {float(r[2]):.1f}s"
            for r in existing_ranges
            if r[1] is not None and r[2] is not None
        )

        clip_duration = runtime_setting(
            "CLIP_TARGET_DURATION"
        )

        prompt = (
            f"Below is a timestamped transcript of a video. "
            f"Select ONE new, distinct highlight moment that "
            f"would make an engaging short-form clip, "
            f"approximately {clip_duration} seconds long. "
            f"Do NOT select a moment overlapping these "
            f"already-used ranges:\n{avoid_ranges or '(none yet)'}\n\n"
            f"Respond ONLY with JSON: an object with 'start' "
            f"and 'end' (numbers, in seconds), 'title' "
            f"(short, engaging), and 'reason' (short string).\n\n"
            f"Transcript:\n{transcript_with_times}"
        )

        data, ai_meta = ai_generate_json(
            prompt, NEW_HOOK_SCHEMA, task="new_hook", max_tokens=8000,
            with_meta=True,
        )

        new_start = float(data["start"])
        new_end = float(data["end"])

        if new_end <= new_start:

            raise HTTPException(
                status_code=502,
                detail="AI returned an invalid time range",
            )

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET start_time = %s,
                        end_time = %s,
                        duration_seconds = %s,
                        title = %s,
                        ai_title = %s,
                        reason = %s,
                        hook_provider = %s,
                        manual_title = NULL,
                        subtitle_override = NULL,
                        status = 'preview_queued',
                        progress = 0,
                        message = 'Queued: rendering new hook',
                        error_stage = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (
                        new_start,
                        new_end,
                        new_end - new_start,
                        data.get("title", "Untitled"),
                        data.get("title", "Untitled"),
                        data.get("reason", ""),
                        ai_meta["provider"],
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {
            "status": "queued",
            "candidate_id": candidate_id,
            "start_seconds": new_start,
            "end_seconds": new_end,
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] new_hook error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# SHARED AI HELPER (used by new-hook, subtitle fix, and
# description copywriting)
# ============================================================

NEW_HOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "number"},
        "end": {"type": "number"},
        "title": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["start", "end", "title", "reason"],
}

SUBTITLE_FIX_SCHEMA = {
    "type": "object",
    "properties": {"fixed": {"type": "string"}},
    "required": ["fixed"],
}

DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
}


def ai_generate_json(prompt: str, schema: dict, *, task: str,
                     max_tokens: int, with_meta: bool = False):
    """shared/ai/router.py call for request handlers. A missing key
    is a 503; every other AI error propagates to the handler's
    generic 500 with its original message. attempts=1 per provider:
    a request handler fails over (auto) instead of sleeping on
    backoff."""
    try:
        return ai_router.ai_generate_json(
            prompt, schema, task=task, max_tokens=max_tokens,
            attempts=1, with_meta=with_meta,
        )
    except AINotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ============================================================
# FIX SUBTITLE WITH AI (correct transcription typos, then
# automatically re-queue the preview so it refreshes with the
# corrected subtitle burned in)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/fix-subtitle-ai"
)
def fix_subtitle_ai(job_id: str, candidate_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT subtitle_override, subtitle_text
                    FROM clip_candidates
                    WHERE id = %s
                      AND job_id = %s
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        current_text = (row[0] or row[1] or "").strip()

        if not current_text:
            raise HTTPException(
                status_code=409,
                detail="No subtitle text to fix yet",
            )

        prompt = (
            "The text below is an Indonesian subtitle for a "
            "short-form video, auto-transcribed from speech and "
            "written in ALL CAPS, one line per subtitle cue. "
            "Speech-to-text transcription may have introduced "
            "typos, misheard words, or wrong punctuation. Fix "
            "ONLY clear transcription mistakes (typos, misheard "
            "words, obvious spelling errors) while preserving: "
            "the exact number of lines, the original meaning and "
            "slang/tone, the ALL CAPS formatting, and the line "
            "order. Do not paraphrase, shorten, or add new "
            "lines.\n\n"
            "Respond ONLY with JSON: "
            '{"fixed": "<corrected text, lines separated by \\n>"}'
            f"\n\nSubtitle:\n{current_text}"
        )

        data = ai_generate_json(
            prompt, SUBTITLE_FIX_SCHEMA, task="subtitle_fix",
            max_tokens=2048,
        )
        fixed_text = str(data.get("fixed", "")).strip()

        if not fixed_text:
            raise HTTPException(
                status_code=502,
                detail="AI returned an empty result",
            )

        # Intentionally NOT written to the database and NOT queued for
        # a preview re-render here. This only suggests a correction —
        # it lands in the subtitle editor's textarea/live preview on
        # the frontend, and is only persisted (and re-rendered) once
        # the user hits "Apply changes", same as any other manual edit
        # to the subtitle text.
        return {
            "status": "ok",
            "candidate_id": candidate_id,
            "subtitle_text": fixed_text,
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] fix_subtitle_ai error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# GENERATE DESCRIPTION WITH AI (Shorts/Reels-ready caption
# copywriting based on the candidate's title, genre, and
# subtitle content)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/generate-description"
)
def generate_description(job_id: str, candidate_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        c.title,
                        c.manual_title,
                        c.ai_title,
                        c.content_type,
                        c.subtitle_override,
                        c.subtitle_text,
                        j.platform
                    FROM clip_candidates c
                    JOIN jobs j ON j.id = c.job_id
                    WHERE c.id = %s
                      AND c.job_id = %s
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        title = row[1] or row[0] or row[2] or "Untitled highlight"
        content_type = row[3] or "Reality"
        subtitle = (row[4] or row[5] or "")[:1500]
        platform = row[6] or "youtube_shorts"

        hashtags = runtime_setting("HASHTAGS", "") or ""
        campaign = runtime_setting("CAMPAIGN_NAME", "") or ""

        platform_label = {
            "youtube_shorts": "YouTube Shorts",
            "instagram_reels": "Instagram Reels",
            "tiktok": "TikTok",
        }.get(platform, "Shorts")

        prompt = (
            f"Write a short, scroll-stopping {platform_label} "
            f"caption/description for a vertical short-form clip.\n"
            f"Genre/mood: {content_type}\n"
            f"Clip title: {title}\n"
            f"Spoken subtitle in the clip (Indonesian): {subtitle}\n\n"
            "Requirements: 1-3 short sentences or a punchy hook "
            "line, native-sounding Indonesian (bilingual is fine "
            "if it reads naturally), no markdown.\n\n"
            "Important: the title and subtitle above are all you "
            "know about this clip's content — you do not know the "
            "specific game, show, or brand name unless it is "
            "explicitly written in them. Do NOT invent, guess, or "
            "reuse a made-up product/game name (e.g. never write "
            "something like \"Riftstorm\" unless that exact word "
            "appears in the title or subtitle above). Talk about "
            "the moment itself instead (e.g. \"gameplay ini\", "
            "\"video ini\", \"match ini\").\n\n"
            "End with 3-6 relevant hashtags"
            + (f" including {hashtags}" if hashtags else "")
            + (
                f", and mention the campaign tag {campaign}"
                if campaign
                else ""
            )
            + ". For any hashtags, only use generic ones tied to "
            "the genre/platform (e.g. #Shorts, #ContentIndonesia, "
            "#Highlights) — never a specific product/game hashtag "
            "unless that name literally appears in the title or "
            "subtitle above."
            + "\n\nRespond ONLY with JSON: "
            '{"description": "<the caption>"}'
        )

        data = ai_generate_json(
            prompt, DESCRIPTION_SCHEMA, task="description",
            max_tokens=1024,
        )
        description = str(data.get("description", "")).strip()

        if not description:
            raise HTTPException(
                status_code=502,
                detail="AI returned an empty result",
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET description = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (description, candidate_id, job_id),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {
            "status": "ok",
            "candidate_id": candidate_id,
            "description": description,
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] generate_description error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# AI THUMBNAILS (Runway) — queue generation, then serve options
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/generate-thumbnails-ai"
)
def generate_thumbnails_ai(job_id: str, candidate_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET status = 'thumbnail_queued',
                        progress = 0,
                        message = 'Queued: generating AI thumbnails',
                        error_stage = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {"status": "queued", "candidate_id": candidate_id}

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] generate_thumbnails_ai error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get(
    "/api/jobs/{job_id}/candidates/{candidate_id}/thumbnail-options/{index}"
)
def get_thumbnail_option(
    job_id: str,
    candidate_id: str,
    index: int,
):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thumbnail_options
                    FROM clip_candidates
                    WHERE id = %s
                      AND job_id = %s
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

        options = (row[0] if row else None) or []

        if not isinstance(options, list) or index < 0 or index >= len(options):
            raise HTTPException(
                status_code=404,
                detail="No thumbnail option at that index",
            )

        path = Path(options[index])

        if not path.is_absolute():
            path = DATA_ROOT / path

        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File missing on disk: {path}",
            )

        return FileResponse(path, media_type="image/jpeg")

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] get_thumbnail_option error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# MANUAL THUMBNAIL UPLOAD
# ============================================================
# Lets the user drop in their own image as an extra thumbnail option,
# alongside the 3 AI-generated ones — picked the same way (via
# selected_thumbnail_index + Apply changes), so it goes through the
# exact same "locked" path and isn't clobbered by the next preview
# render.

THUMBNAIL_UPLOAD_MAX_BYTES = 8 * 1024 * 1024


@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/thumbnail-upload"
)
async def upload_manual_thumbnail(
    job_id: str,
    candidate_id: str,
    file: UploadFile = File(...),
):

    try:

        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be an image",
            )

        raw = await file.read()

        if not raw:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        if len(raw) > THUMBNAIL_UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Image is too large (max 8MB)",
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thumbnail_options
                    FROM clip_candidates
                    WHERE id = %s AND job_id = %s
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        options = list(row[0] or [])

        thumb_dir = DATA_ROOT / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        out_path = (
            thumb_dir
            / f"{candidate_id}_manual_{uuid.uuid4().hex[:8]}.jpg"
        )

        # Re-encode to JPEG (matching every other thumbnail option) via
        # Pillow when it's available; otherwise fall back to writing
        # the raw bytes as-is so the upload still works.
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.save(out_path, "JPEG", quality=92)

        except Exception:
            out_path.write_bytes(raw)

        relative_path = str(out_path.relative_to(DATA_ROOT))
        options.append(relative_path)
        new_index = len(options) - 1

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET thumbnail_options = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s AND job_id = %s
                    RETURNING id
                    """,
                    (
                        json_param(options),
                        candidate_id,
                        job_id,
                    ),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {
            "status": "ok",
            "candidate_id": candidate_id,
            "thumbnail_options": options,
            "index": new_index,
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] upload_manual_thumbnail error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# WATERMARK ASSETS (upload + choose which one renders)
# ============================================================
# A small asset library so the watermark is a choice made in the UI
# instead of a file baked into the container image. Falls back to
# worker.py's baked-in default (/app/assets/watermark.png) until at
# least one asset has been uploaded and activated.

WATERMARK_UPLOAD_MAX_BYTES = 5 * 1024 * 1024


@app.get("/api/assets/watermarks")
def list_watermark_assets():

    try:

        active_id = runtime_setting("ACTIVE_WATERMARK_ID") or ""

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename, width, height, created_at
                    FROM watermark_assets
                    ORDER BY created_at DESC
                    """
                )
                rows = cur.fetchall()

        return {
            "active_id": active_id or None,
            "assets": [
                {
                    "id": r[0],
                    "filename": r[1],
                    "width": r[2],
                    "height": r[3],
                    "created_at": r[4].isoformat() if r[4] else None,
                    "active": r[0] == active_id,
                }
                for r in rows
            ],
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/assets/watermarks")
async def upload_watermark_asset(file: UploadFile = File(...)):

    try:

        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be an image",
            )

        raw = await file.read()

        if not raw:
            raise HTTPException(
                status_code=400, detail="Uploaded file is empty"
            )

        if len(raw) > WATERMARK_UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=400, detail="Image is too large (max 5MB)"
            )

        asset_id = str(uuid.uuid4())
        wm_dir = DATA_ROOT / "watermarks"
        wm_dir.mkdir(parents=True, exist_ok=True)
        out_path = wm_dir / f"{asset_id}.png"

        width = height = None

        # PNG keeps alpha transparency, which matters for a watermark
        # overlay — re-encode with Pillow when available, matching the
        # manual-thumbnail-upload behavior; fall back to raw bytes
        # (still works if the source was already a PNG).
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(raw))
            img = img.convert("RGBA")
            width, height = img.size
            img.save(out_path, "PNG")

        except Exception:
            out_path.write_bytes(raw)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO watermark_assets
                        (id, filename, path, width, height)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        asset_id,
                        file.filename or "watermark.png",
                        str(out_path.relative_to(DATA_ROOT)),
                        width,
                        height,
                    ),
                )

                # First asset ever uploaded becomes active automatically
                # — otherwise uploading would silently do nothing until
                # the user also remembers to activate it.
                cur.execute(
                    "SELECT COUNT(*) FROM watermark_assets"
                )
                count = cur.fetchone()[0]

                if count == 1:
                    cur.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES ('ACTIVE_WATERMARK_ID', %s, NOW())
                        ON CONFLICT (key) DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = NOW()
                        """,
                        (asset_id,),
                    )

            conn.commit()

        return {
            "status": "ok",
            "id": asset_id,
            "filename": file.filename,
            "width": width,
            "height": height,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/assets/watermarks/{asset_id}/activate")
def activate_watermark_asset(asset_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM watermark_assets WHERE id = %s",
                    (asset_id,),
                )
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=404, detail="Watermark asset not found"
                    )

                cur.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES ('ACTIVE_WATERMARK_ID', %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = NOW()
                    """,
                    (asset_id,),
                )

            conn.commit()

        return {"status": "ok", "active_id": asset_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/assets/watermarks/{asset_id}")
def delete_watermark_asset(asset_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT path FROM watermark_assets WHERE id = %s",
                    (asset_id,),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404, detail="Watermark asset not found"
                    )

                cur.execute(
                    "DELETE FROM watermark_assets WHERE id = %s",
                    (asset_id,),
                )

                active_id = runtime_setting("ACTIVE_WATERMARK_ID") or ""
                if active_id == asset_id:
                    cur.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES ('ACTIVE_WATERMARK_ID', '', NOW())
                        ON CONFLICT (key) DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = NOW()
                        """
                    )

            conn.commit()

        try:
            (DATA_ROOT / row[0]).unlink(missing_ok=True)
        except Exception:
            pass

        return {"status": "ok"}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/assets/watermarks/{asset_id}/file")
def get_watermark_asset_file(asset_id: str):

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT path FROM watermark_assets WHERE id = %s",
                (asset_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Watermark asset not found")

    path = DATA_ROOT / row[0]

    if not path.exists():
        raise HTTPException(status_code=404, detail="Watermark file missing")

    return FileResponse(path, media_type="image/png")


# ============================================================
# CANDIDATE VERSION HISTORY
# ============================================================
# A lightweight changelog, not a full undo system: every time a
# candidate's edits are actually committed (Apply changes, Final
# render, Submagic apply), we snapshot what it looked like at that
# moment. Restoring only ever touches this ONE candidate's own
# fields (subtitle text, description, thumbnail) — it deliberately
# never restores job-level subtitle_style/font/size/animation, since
# those are shared across every candidate in the job and silently
# rewriting them from one candidate's history would change how
# unrelated candidates render too. The snapshot still records what
# style/font/animation were active at the time, for reference.


def record_candidate_version(cur, candidate_id: str, label: str):
    """
    Call with an already-open cursor inside the same transaction as
    the change being recorded, so the version reflects exactly what
    was just committed. Best-effort: swallows its own errors so a
    versioning hiccup never blocks the actual save.
    """

    try:

        cur.execute(
            """
            SELECT
                c.subtitle_override,
                c.description,
                c.thumbnail_path,
                c.manual_title,
                c.rating,
                j.subtitle_style,
                j.subtitle_font,
                j.subtitle_size,
                j.subtitle_animation,
                j.layout
            FROM clip_candidates c
            JOIN jobs j ON j.id = c.job_id
            WHERE c.id = %s
            """,
            (candidate_id,),
        )
        row = cur.fetchone()

        if not row:
            return

        snapshot = {
            "subtitle_override": row[0],
            "description": row[1],
            "thumbnail_path": row[2],
            "manual_title": row[3],
            "rating": row[4],
            "subtitle_style": row[5],
            "subtitle_font": row[6],
            "subtitle_size": row[7],
            "subtitle_animation": row[8],
            "layout": row[9],
        }

        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM candidate_versions "
            "WHERE candidate_id = %s",
            (candidate_id,),
        )
        next_version = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO candidate_versions
                (id, candidate_id, version, label, snapshot)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                candidate_id,
                next_version,
                label,
                json_param(snapshot),
            ),
        )

    except Exception as exc:
        print("[backend] record_candidate_version failed:", exc)


@app.get(
    "/api/jobs/{job_id}/candidates/{candidate_id}/versions"
)
def list_candidate_versions(job_id: str, candidate_id: str):

    try:

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cv.version, cv.label, cv.snapshot, cv.created_at
                    FROM candidate_versions cv
                    JOIN clip_candidates c ON c.id = cv.candidate_id
                    WHERE cv.candidate_id = %s AND c.job_id = %s
                    ORDER BY cv.version DESC
                    """,
                    (candidate_id, job_id),
                )
                rows = cur.fetchall()

        return {
            "versions": [
                {
                    "version": r[0],
                    "label": r[1],
                    "snapshot": r[2],
                    "created_at": r[3].isoformat() if r[3] else None,
                }
                for r in rows
            ]
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/versions/{version}/restore"
)
def restore_candidate_version(job_id: str, candidate_id: str, version: int):
    """
    Restores this candidate's own fields (subtitle text, description,
    thumbnail) from a past version, then queues a preview re-render so
    the restored look actually shows up. Job-level style/font/size/
    animation are NOT restored — see the module note above.
    """

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT cv.snapshot
                    FROM candidate_versions cv
                    JOIN clip_candidates c ON c.id = cv.candidate_id
                    WHERE cv.candidate_id = %s
                      AND c.job_id = %s
                      AND cv.version = %s
                    """,
                    (candidate_id, job_id, version),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404, detail="Version not found"
                    )

                snapshot = row[0] or {}

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET subtitle_override = %s,
                        description = %s,
                        thumbnail_path = %s,
                        thumbnail_locked = TRUE,
                        manual_title = %s,
                        status = 'preview_queued',
                        progress = 0,
                        message = 'Queued: restoring version ' || %s,
                        updated_at = NOW()
                    WHERE id = %s AND job_id = %s
                    RETURNING id
                    """,
                    (
                        snapshot.get("subtitle_override"),
                        snapshot.get("description"),
                        snapshot.get("thumbnail_path"),
                        snapshot.get("manual_title"),
                        str(version),
                        candidate_id,
                        job_id,
                    ),
                )

                if not cur.fetchone():
                    raise HTTPException(
                        status_code=404, detail="Candidate not found"
                    )

                record_candidate_version(
                    cur, candidate_id, f"Restored version {version}"
                )

            conn.commit()

        return {"status": "preview_queued", "restored_version": version}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# SUBMAGIC INTEGRATION (optional, opt-in per candidate)
# ============================================================
# Runs alongside the native subtitle/thumbnail pipeline, never in
# place of it. Nothing here touches a candidate's native `status`,
# `final_path`, etc. until the user explicitly calls "use-as-final"
# on a completed Submagic render. All the actual HTTP work (upload,
# poll, export, download) happens in worker.py's claim_submagic_task()
# / claim_submagic_poll() — these endpoints just flip a queue flag.

SUBMAGIC_BUSY_STATES = {
    "queued_upload",
    "uploading",
    "transcribing",
    "queued_export",
    "exporting",
    "queued_apply",
    "applying",
}


@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/submagic/start"
)
def submagic_start(job_id: str, candidate_id: str):
    """
    Kicks off an opt-in Submagic pass for this one candidate: uploads
    the current preview render and transcribes it (autoRender: false
    on Submagic's side — no billable render yet). Requires
    SUBMAGIC_API_KEY to be configured in Settings.
    """

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET submagic_status = 'queued_upload',
                        submagic_error = NULL,
                        submagic_project_id = NULL,
                        submagic_preview_url = NULL,
                        submagic_download_url = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                      AND (
                        submagic_status IS NULL
                        OR submagic_status IN ('failed', 'completed', 'applied')
                      )
                    RETURNING id
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "A Submagic pass is already running or the "
                            "candidate wasn't found"
                        ),
                    )

            conn.commit()

        return {"status": "queued_upload", "candidate_id": candidate_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/submagic/export"
)
def submagic_export(job_id: str, candidate_id: str):
    """
    Triggers Submagic's actual render (billable on their side) for a
    candidate whose transcript is ready. This is the "decide to
    commit" step — nothing renders on Submagic until this is called.
    """

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET submagic_status = 'queued_export',
                        submagic_error = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                      AND submagic_status = 'transcribed'
                    RETURNING id
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "This candidate isn't ready to export yet — "
                            "run Submagic transcription first"
                        ),
                    )

            conn.commit()

        return {"status": "queued_export", "candidate_id": candidate_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/submagic/use-as-final"
)
def submagic_use_as_final(job_id: str, candidate_id: str):
    """
    Adopts a completed Submagic render as this candidate's final
    video — downloaded and stored locally, same as a native final
    render. Only available once you've actually reviewed the
    Submagic output (previewUrl/downloadUrl) and decided you like it.
    """

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clip_candidates
                    SET submagic_status = 'queued_apply',
                        updated_at = NOW()
                    WHERE id = %s
                      AND job_id = %s
                      AND submagic_status = 'completed'
                    RETURNING id
                    """,
                    (candidate_id, job_id),
                )
                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "No completed Submagic render for this "
                            "candidate yet"
                        ),
                    )

                record_candidate_version(
                    cur, candidate_id, "Submagic render requested"
                )

            conn.commit()

        return {"status": "queued_apply", "candidate_id": candidate_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# UPLOAD TO YOUTUBE (requires OAuth setup — see setup notes)
# ============================================================

@app.post(
    "/api/jobs/{job_id}/candidates/{candidate_id}/upload-youtube"
)
def upload_to_youtube(
    job_id: str,
    candidate_id: str,
):

    client_id = runtime_setting("YOUTUBE_CLIENT_ID")
    client_secret = runtime_setting("YOUTUBE_CLIENT_SECRET")
    refresh_token = runtime_setting("YOUTUBE_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):

        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube upload isn't configured yet. "
                "Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                "and YOUTUBE_REFRESH_TOKEN to enable this."
            ),
        )

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        final_path,
                        render_path,
                        title,
                        manual_title,
                        subtitle_text,
                        subtitle_override,
                        description
                    FROM clip_candidates
                    WHERE id = %s
                      AND job_id = %s
                    """,
                    (
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        video_path = row[0] or row[1]

        if not video_path:

            raise HTTPException(
                status_code=409,
                detail="No final render exists for this candidate yet. Approve it first.",
            )

        path = Path(video_path)

        if not path.is_absolute():
            path = DATA_ROOT / video_path

        if not path.exists():

            raise HTTPException(
                status_code=404,
                detail=f"Final file missing on disk: {path}",
            )

        # ------------------------------------------------------
        # Actual upload via the YouTube Data API v3.
        # Uncomment once google-auth + google-api-python-client
        # are added to backend/requirements.txt and the OAuth
        # credentials above are confirmed working end-to-end.
        # ------------------------------------------------------
        #
        # from google.oauth2.credentials import Credentials
        # from googleapiclient.discovery import build
        # from googleapiclient.http import MediaFileUpload
        #
        # creds = Credentials(
        #     None,
        #     refresh_token=refresh_token,
        #     token_uri="https://oauth2.googleapis.com/token",
        #     client_id=client_id,
        #     client_secret=client_secret,
        # )
        #
        # youtube = build("youtube", "v3", credentials=creds)
        #
        # title = row[3] or row[2] or "AI Short"
        # description = row[6] or row[5] or row[4] or ""
        #
        # request_body = {
        #     "snippet": {
        #         "title": title[:100],
        #         "description": description,
        #         "categoryId": "20",
        #     },
        #     "status": {
        #         "privacyStatus": "private",
        #         "selfDeclaredMadeForKids": False,
        #     },
        # }
        #
        # media = MediaFileUpload(
        #     str(path), chunksize=-1, resumable=True
        # )
        #
        # response = youtube.videos().insert(
        #     part="snippet,status",
        #     body=request_body,
        #     media_body=media,
        # ).execute()
        #
        # video_url = f"https://youtube.com/watch?v={response['id']}"
        #
        # return {"status": "uploaded", "video_url": video_url}

        raise HTTPException(
            status_code=501,
            detail=(
                "YouTube credentials are set, but the upload "
                "call is still commented out pending your "
                "confirmation this OAuth setup has been "
                "tested. See backend/app/main.py for the "
                "ready-to-enable code."
            ),
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] upload_to_youtube error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# DELETE CANDIDATE
# ============================================================

@app.delete(
    "/api/jobs/{job_id}/candidates/{candidate_id}"
)
def delete_candidate(
    job_id: str,
    candidate_id: str,
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM clip_candidates
                    WHERE id = %s
                      AND job_id = %s
                    RETURNING id
                    """,
                    (
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Candidate not found",
                    )

            conn.commit()

        return {
            "status": "deleted",
            "candidate_id": candidate_id,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# SERVE CANDIDATE MEDIA
# ============================================================

def _serve_candidate_file(
    job_id: str,
    candidate_id: str,
    primary_column: str,
    fallback_column: Optional[str] = None,
    media_type: str = "video/mp4",
):

    columns = [primary_column]

    if fallback_column:
        columns.append(fallback_column)

    select_columns = ", ".join(columns)

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    f"""
                    SELECT {select_columns}
                    FROM clip_candidates
                    WHERE id = %s
                      AND job_id = %s
                    """,
                    (
                        candidate_id,
                        job_id,
                    ),
                )

                row = cur.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        raw_path = row[0]

        if not raw_path and fallback_column:
            raw_path = row[1]

        if not raw_path:

            raise HTTPException(
                status_code=404,
                detail="No file has been rendered for this candidate yet",
            )

        path = Path(raw_path)

        if not path.is_absolute():
            path = DATA_ROOT / raw_path

        if not path.exists():

            raise HTTPException(
                status_code=404,
                detail=f"File missing on disk: {path}",
            )

        return FileResponse(
            path,
            media_type=media_type,
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] serve_candidate_file error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get(
    "/api/jobs/{job_id}/candidates/{candidate_id}/preview"
)
def get_candidate_preview(
    job_id: str,
    candidate_id: str,
):

    return _serve_candidate_file(
        job_id,
        candidate_id,
        "preview_path",
    )


@app.get(
    "/api/jobs/{job_id}/candidates/{candidate_id}/render"
)
def get_candidate_render(
    job_id: str,
    candidate_id: str,
):

    return _serve_candidate_file(
        job_id,
        candidate_id,
        "final_path",
        fallback_column="render_path",
    )


@app.get(
    "/api/jobs/{job_id}/candidates/{candidate_id}/thumbnail"
)
def get_candidate_thumbnail(
    job_id: str,
    candidate_id: str,
):
    return _serve_candidate_file(
        job_id,
        candidate_id,
        "thumbnail_path",
        media_type="image/jpeg",
    )


# ============================================================
# APP SETTINGS
# ============================================================

@app.get("/api/settings")
def get_settings():
    try:
        # Effective value (DB -> env -> default), i.e. what the
        # worker will actually use, plus where it came from.
        _settings.invalidate()
        result = {}

        for key in DEFAULT_SETTINGS:
            value, source = _settings.resolve(key)
            if key in SECRET_SETTING_KEYS and value:
                result[key] = {
                    "value": "••••••••",
                    "configured": True,
                    "source": source,
                }
            else:
                result[key] = {
                    "value": value,
                    "configured": bool(value),
                    "source": source,
                }

        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/settings")
def update_settings(req: SettingsUpdate):
    unknown = [k for k in req.values if k not in DEFAULT_SETTINGS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting key(s): {unknown}",
        )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for key, value in req.values.items():
                    if value == "••••••••":
                        continue
                    cur.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (key)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = NOW()
                        """,
                        (key, str(value)),
                    )
            conn.commit()

        _settings.invalidate()

        return {"status": "ok"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# QUEUE / CURRENT JOB MANAGEMENT
# ============================================================

@app.post("/api/jobs/{job_id}/move-to-queue")
def move_job_to_queue(job_id: str):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'paused',
                        message = 'Paused in Clip Queue',
                        updated_at = NOW()
                    WHERE id = %s
                      AND status NOT IN ('completed','failed','cancelled')
                    RETURNING id
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Current job not found or already finished",
                    )
            conn.commit()
        return {"status": "queued", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/jobs/{job_id}/restore")
def restore_job(job_id: str):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = CASE
                            WHEN transcript IS NULL OR transcript = ''
                            THEN 'queued'
                            ELSE 'reanalyze_queued'
                        END,
                        message = 'Restored to Current Job',
                        error_stage = NULL,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'paused'
                    RETURNING id, status
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Queued job not found",
                    )
            conn.commit()
        return {"status": "restored", "job_id": job_id, "job_status": row[1]}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# DELETE JOB
# ============================================================

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):

    try:

        removed_files = []

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )

                if not cur.fetchone():

                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

                # ------------------------------------------------
                # Collect every file path referenced by this job's
                # candidates and their rendered clips, before the
                # DB rows are cascade-deleted below.
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        c.preview_path,
                        c.render_path,
                        c.final_path,
                        r.output_path
                    FROM clip_candidates c
                    LEFT JOIN rendered_clips r
                        ON r.candidate_id = c.id
                    WHERE c.job_id = %s
                    """,
                    (job_id,),
                )

                path_rows = cur.fetchall()

                for row in path_rows:

                    for raw_path in row:

                        if not raw_path:
                            continue

                        path = Path(raw_path)

                        if not path.is_absolute():
                            path = DATA_ROOT / raw_path

                        try:

                            path.unlink()
                            removed_files.append(str(path))

                        except FileNotFoundError:

                            pass

                        except Exception:

                            print(
                                "[backend] delete_job file "
                                "cleanup warning:",
                                traceback.format_exc(),
                            )

                # ------------------------------------------------
                # Delete the job. clip_candidates and their
                # rendered_clips cascade-delete automatically via
                # ON DELETE CASCADE. source_videos is intentionally
                # left untouched: youtube_url is unique on that
                # table, so a source video is likely shared/reused
                # across jobs, and it's also referenced separately
                # by the transcripts table.
                # ------------------------------------------------

                cur.execute(
                    """
                    DELETE FROM jobs
                    WHERE id = %s
                    RETURNING id
                    """,
                    (job_id,),
                )

                row = cur.fetchone()

                if not row:

                    raise HTTPException(
                        status_code=404,
                        detail="Job not found",
                    )

            conn.commit()

        return {
            "status": "deleted",
            "job_id": job_id,
            "files_removed": removed_files,
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "[backend] delete_job error:",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# ERROR HANDLER HELPER
# ============================================================

def mark_job_failed(
    job_id: str,
    stage: str,
    message: str,
):

    try:

        with get_db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE jobs
                    SET
                        status = 'failed',
                        error_stage = %s,
                        error_message = %s,
                        message = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        stage,
                        message,
                        message,
                        job_id,
                    ),
                )

            conn.commit()

    except Exception:

        print(
            "[backend] Failed to update job error:",
            traceback.format_exc(),
        )