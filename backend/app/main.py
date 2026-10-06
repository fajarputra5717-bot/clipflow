import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import statistics
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Optional

import psycopg
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import auth

from shared.ai import router as ai_router
from shared import campaigns, descriptions, edit_spec as edit_specs, languages, posts as post_rules, rule_checks
from shared.errors import AINotConfiguredError
from shared.fonts import normalize_caption_font
from shared.settings import (
    DEFAULT_SETTINGS,
    SECRET_SETTING_KEYS,
    USER_ONLY_KEYS,
    USER_SETTING_KEYS,
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
# AUTH (P1.5, replaces R-03's single key) — every /api/* request needs
# a principal, resolved once by the middleware into request.state.user
# ({id, username, role}); see app/auth.py:
#   1. session cookie (browser login; HttpOnly, SameSite=Lax, DB row),
#   2. a per-user API token `cf_…` (part 4) in X-ClipFlow-Key or
#      Authorization: Bearer (scripts; hashed in api_tokens). The old
#      shared CLIPFLOW_API_KEY is gone (127): any other value is 401,
#   3. ?mt= per-user media token, GET/HEAD on MEDIA_PATH_RE only.
# Open: /api/auth/login, /api/auth/logout, /health, /. Middleware (not a
# route dependency) so unknown /api paths also get 401. Cookie-authed
# writes must come from an allowed Origin (CSRF belt to SameSite=Lax).
# ============================================================

API_KEY_HEADER = "X-ClipFlow-Key"

MEDIA_TOKEN_PARAM = "mt"

MEDIA_PATH_RE = re.compile(
    r"^/api/("
    r"jobs/[^/]+/candidates/[^/]+/"
    r"(preview|render|thumbnail|thumbnail-options/\d+)"
    r"|assets/watermarks/[^/]+/file"
    r")$"
)

OPEN_API_PATHS = {"/api/auth/login", "/api/auth/logout"}
OPEN_API_PATHS = OPEN_API_PATHS | {"/api/env"}  # lane-b hook: staging banner (no secrets)

# Part 5: a session whose password was set by an admin (create/reset) may only
# do these until it picks its own password.
PASSWORD_CHANGE_PATHS = {"/api/auth/me", "/api/auth/password"}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Ownership guard (P1.5): every route under these prefixes names a row by id; the
# middleware 404s unless the row belongs to the caller, so no handler can forget.
JOB_PATH_RE = re.compile(r"^/api/jobs/([^/]+)(?:/candidates/([^/]+))?(?:/|$)")
WATERMARK_PATH_RE = re.compile(r"^/api/assets/watermarks/([^/]+)(?:/|$)")
ACCOUNT_PATH_RE = re.compile(r"^/api/accounts/([^/]+)(?:/|$)")
POST_PATH_RE = re.compile(r"^/api/posts/([^/]+)(?:/|$)")


def _path_owned(user: dict, path: str) -> bool:
    m = JOB_PATH_RE.match(path)
    w = WATERMARK_PATH_RE.match(path)
    a = ACCOUNT_PATH_RE.match(path)
    po = POST_PATH_RE.match(path)
    if not m and not w and not a and not po:
        return True
    with get_db() as conn:
        with conn.cursor() as cur:
            if m:
                job_id, candidate_id = m.groups()
                cur.execute("SELECT 1 FROM jobs WHERE id = %s AND user_id = %s", (job_id, user["id"]))
                if not cur.fetchone():
                    return False
                if candidate_id:
                    cur.execute(
                        "SELECT 1 FROM clip_candidates WHERE id::text = %s AND job_id = %s",
                        (candidate_id, job_id),
                    )
                    return bool(cur.fetchone())
                return True
            if a:
                cur.execute(
                    "SELECT 1 FROM platform_accounts WHERE id = %s AND user_id = %s",
                    (a.group(1), user["id"]),
                )
                return bool(cur.fetchone())
            if po:
                cur.execute(
                    "SELECT 1 FROM clip_posts WHERE id = %s AND user_id = %s",
                    (po.group(1), user["id"]),
                )
                return bool(cur.fetchone())
            cur.execute(
                "SELECT 1 FROM watermark_assets WHERE id::text = %s AND user_id = %s",
                (w.group(1), user["id"]),
            )
            return bool(cur.fetchone())


def _resolve_principal(request: Request) -> Optional[dict]:
    with get_db() as conn:
        token = request.cookies.get(auth.SESSION_COOKIE, "")
        if token:
            user = auth.session_user(conn, token)
            if user:
                user["via"] = "session"
                return user

        supplied = request.headers.get(API_KEY_HEADER, "")
        bearer = request.headers.get("authorization", "")
        if bearer[:7].lower() == "bearer ":
            supplied = supplied or bearer[7:].strip()
        if supplied:
            # Only per-user tokens; the shared CLIPFLOW_API_KEY was removed (127).
            user = auth.api_token_user(conn, supplied)
            if user:
                user["via"] = "api_token"
                return user
            return None

        mt = request.query_params.get(MEDIA_TOKEN_PARAM, "")
        if (
            mt
            and request.method in ("GET", "HEAD")
            and MEDIA_PATH_RE.match(request.url.path)
        ):
            uid = auth.media_token_user_id(conn, mt)
            user = auth.active_user(conn, uid) if uid else None
            if user:
                user["via"] = "media_token"
                return user
    return None


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    origin = origin.rstrip("/")
    host = request.headers.get("host", "")
    if urlsplit(origin).netloc == host:
        return True
    return origin in cors_allowed_origins()


@app.middleware("http")
async def require_user(request: Request, call_next):
    path = request.url.path
    request.state.user = None
    if (path == "/api" or path.startswith("/api/")) and path not in OPEN_API_PATHS:
        try:
            user = await run_in_threadpool(_resolve_principal, request)
        except Exception:
            print("[auth] principal lookup failed:", traceback.format_exc())
            user = None
        if not user:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        if (
            user["via"] == "session"
            and request.method not in SAFE_METHODS
            and not _origin_allowed(request)
        ):
            return JSONResponse({"detail": "Cross-origin request refused"}, status_code=403)
        if user.get("must_change_password") and path not in PASSWORD_CHANGE_PATHS:
            return JSONResponse(
                {"detail": "Choose a new password first", "code": "password_change_required"},
                status_code=403,
            )
        if (path == "/api/admin" or path.startswith("/api/admin/")) and user["role"] != "admin":
            return JSONResponse({"detail": "Admins only"}, status_code=403)
        try:
            owned = await run_in_threadpool(_path_owned, user, path)
        except Exception:
            print("[auth] ownership check failed:", traceback.format_exc())
            owned = False
        if not owned:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        request.state.user = user
    return await call_next(request)


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user


# CORS: explicit origin list from env CORS_ALLOWED_ORIGINS (comma
# separated), never "*". No credentials: cross-origin callers use a
# header token; the session cookie is same-origin only. Added AFTER the
# auth middleware so it wraps it: preflights are answered here and 401s
# still carry CORS headers.
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
    allow_headers=["Content-Type", API_KEY_HEADER, "Authorization"],
)
from app import routes_editor; app.include_router(routes_editor.router)  # lane-b hook


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
        # R-05: per-job watermark; NULL = global WATERMARK_* setting.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS watermark_width INT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS watermark_opacity REAL",
        # R-09: FALSE renders preview/final without burned-in captions.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS burn_subtitles BOOLEAN DEFAULT TRUE",
        # R-15 failure recovery: heartbeat of the claiming worker, attempt
        # counter, transient/permanent class, earliest automatic retry.
        # R-17: positions stored per job at creation; NULL = legacy layout.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS watermark_position_y REAL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS subtitle_seam_gap REAL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS attempts INT NOT NULL DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_class TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS retry_after TIMESTAMPTZ",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS attempts INT NOT NULL DEFAULT 0",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS error_class TEXT",
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS retry_after TIMESTAMPTZ",
        # 079: per-job language. language = requested (auto|en|id, NULL = pre-079 job, Indonesian);
        # language_fallback = the form's last explicit choice for a low-confidence Auto;
        # effective_language = what the pipeline used (read via shared.languages.job_language).
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS language TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS language_fallback TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS detected_language TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS language_confidence REAL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS effective_language TEXT",
        # 081: campaign slug (docs/campaigns/<slug>.rules.json; NULL = none) and the
        # campaign's watermark asset, snapshotted at creation like R-05/R-17.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS campaign TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS watermark_asset_id TEXT",
        # P0: [{code, message, at}] non-fatal render problems shown as chips
        # (loudness failed, campaign watermark missing).
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS render_warnings JSONB",
        # P0: one facecam layout per job: {mode: panel|full, detected, total, fallback}
        # (worker decide_face_layout); NULL = each clip decides.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS face_layout JSONB",
        # Pre-P1 #1: why the campaign watermark couldn't be resolved at job
        # creation (NULL = fine). The worker renders WITHOUT a watermark + chip.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS watermark_failure TEXT",
        # 108 (P1): per-clip edits (shared/edit_spec.py); NULL = job-level behaviour.
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS edit_spec JSONB",
        # 109 (P1): content-safety pass {flags:[{rule, quote, reason}], checked_at,
        # provider, model, text_hash, dismissed}; warning only (worker writes it).
        "ALTER TABLE clip_candidates ADD COLUMN IF NOT EXISTS safety_check JSONB",
        # P1.5: users, DB sessions, login failures, server secrets (app/auth.py).
        *auth.SCHEMA,
        # P1.5 ownership: every user-owned table carries user_id (candidates via their job).
        # Legacy rows are assigned to the bootstrap admin at startup, then NOT NULL.
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id, created_at DESC)",
        "ALTER TABLE watermark_assets ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id)",
        "CREATE INDEX IF NOT EXISTS idx_watermark_assets_user ON watermark_assets (user_id)",
        # P2 part 1 (128): the user's own posting accounts per platform (rule_checks.PLATFORM_LIMITS keys).
        """
        CREATE TABLE IF NOT EXISTS platform_accounts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            handle TEXT NOT NULL,
            note TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_accounts ON platform_accounts (user_id, platform, lower(handle))",
        # P2 part 2 (129): one row per clip per platform post (shared/posts.py rules). The contract the manual
        # flow, the future auto-poster (source=auto, external_id, error) and the view tracker write to.
        # candidate_id SET NULL + job/campaign/title snapshots keep post + money history if a job is deleted;
        # account RESTRICT: an account with posts is paused, never deleted.
        """
        CREATE TABLE IF NOT EXISTS clip_posts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            candidate_id TEXT REFERENCES clip_candidates(id) ON DELETE SET NULL,
            job_id TEXT,
            campaign TEXT,
            title TEXT,
            platform TEXT NOT NULL,
            account_id TEXT REFERENCES platform_accounts(id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned','posted','claimed','paid','dropped')),
            source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','auto')),
            scheduled_for TIMESTAMPTZ,
            posted_at TIMESTAMPTZ,
            url TEXT,
            external_id TEXT,
            views BIGINT,
            views_at TIMESTAMPTZ,
            claimed_at TIMESTAMPTZ,
            paid_at TIMESTAMPTZ,
            paid_rp BIGINT,
            note TEXT,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_clip_posts_user ON clip_posts (user_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_clip_posts_candidate ON clip_posts (candidate_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clip_posts_url ON clip_posts (user_id, url) WHERE url IS NOT NULL",
        # A clip goes to one account once (re-post = drop the old row first).
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clip_posts_account ON clip_posts (candidate_id, account_id) "
        "WHERE account_id IS NOT NULL AND status <> 'dropped'",
        # P1.5 part 3: per-user values for USER_SETTING_KEYS (shared/settings.py).
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, key)
        )
        """,
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

    try:
        with get_db() as conn:
            admin_id = auth.ensure_bootstrap_admin(conn)
            if admin_id:
                assign_legacy_rows(conn, admin_id)
    except Exception:
        print("[auth] bootstrap admin failed:", traceback.format_exc())


OWNED_TABLES = ("jobs", "watermark_assets")


def assign_legacy_rows(conn, admin_id: str) -> None:
    """P1.5 first run: rows from before accounts belong to the bootstrap admin."""
    for table in OWNED_TABLES:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {table} SET user_id = %s WHERE user_id IS NULL", (admin_id,))
            if cur.rowcount:
                print(f"[auth] {cur.rowcount} legacy {table} rows assigned to the bootstrap admin")
            cur.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")
        conn.commit()
    # Part 3: user-only settings (they name an owned row) move from the global
    # app_settings to the bootstrap admin, whose asset they point at.
    with conn.cursor() as cur:
        for key in USER_ONLY_KEYS:
            cur.execute(
                """
                INSERT INTO user_settings (user_id, key, value)
                SELECT %s, key, value FROM app_settings WHERE key = %s AND COALESCE(value, '') <> ''
                ON CONFLICT (user_id, key) DO NOTHING
                """,
                (admin_id, key),
            )
            cur.execute("DELETE FROM app_settings WHERE key = %s", (key,))
            if cur.rowcount:
                print(f"[auth] global {key} moved to the bootstrap admin's user settings")
    conn.commit()


def set_user_setting(cur, user_id: str, key: str, value: Optional[str]) -> None:
    """Empty/None = unset (falls back to the global value, or none for USER_ONLY_KEYS)."""
    if value is None or str(value).strip() == "":
        cur.execute("DELETE FROM user_settings WHERE user_id = %s AND key = %s", (user_id, key))
        return
    cur.execute(
        """
        INSERT INTO user_settings (user_id, key, value, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        (user_id, key, str(value)),
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
# Preset names make_ass() knows (worker.py `styles`), mirrored by
# SUBTITLE_STYLES in index.html. Keep all three in sync.
SUBTITLE_STYLE_PRESETS = {
    "bold", "outline", "clean", "boxed", "hormozi",
    "neon", "minimal", "impact", "pastel", "gold",
}

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

        # The edit panel's "Font style" select sends a preset name
        # as a plain string. The baseline treated it as a font name,
        # so the preset never changed on Apply (fixed with R-05).
        if value_lower in SUBTITLE_STYLE_PRESETS:
            style["style"] = value_lower

        # Compatibility with old frontend values
        elif value_lower == "bold":
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

    # Sanitize fields. The font must be one the worker can render
    # (shared/fonts.py); an unknown name falls back to the default,
    # loudly, so a dropped font choice shows up in the logs (R-19).
    style["font"], known_font = normalize_caption_font(
        style.get("font")
    )

    if not known_font:
        print(
            "[backend] unknown subtitle font "
            f"{str(font or value)[:60]!r}; using {style['font']}"
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

    # 117: omitted = the campaign's default_layout (else "auto"); the UI sends an explicit choice.
    layout: Optional[str] = None

    platform: str = "youtube_shorts"

    # 079: auto | en | id. language_fallback = the user's last explicit choice
    # on the Import form, used when Auto-detect confidence is low.
    # QA #5: omitted (API callers) = the WHISPER_LANGUAGE setting, as before 079.
    language: Optional[str] = None

    language_fallback: Optional[str] = None

    # 081: campaign slug (GET /api/campaigns); None = no campaign.
    campaign: Optional[str] = None

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

    # 108: merged into clip_candidates.edit_spec; a key sent as null is removed.
    edit_spec: Optional[dict] = None


class CaptionPresetAll(BaseModel):
    style: str
    animation: str


class JobUpdate(BaseModel):
    custom_title: Optional[str] = None


class RenderOptionsUpdate(BaseModel):
    # Only fields present in the request body are written; an
    # explicit null resets to the global default.
    watermark_width: Optional[int] = Field(default=None, ge=100, le=1080)
    watermark_opacity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # R-09. Only changes what gets rendered: subtitle text/style stay.
    burn_subtitles: Optional[bool] = None


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
    "none",  # QA #6: no facecam → full-frame crop, no bottom panel
}

# yt-dlp fetches whatever it is given (SSRF) and parses a leading "-"
# as one of its own options (audit-001 F4), so only https YouTube URLs
# reach the worker.
YOUTUBE_URL_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def validate_youtube_url(raw):
    url = (raw or "").strip()
    error = (
        "youtube_url must be an https:// link on youtube.com, "
        "www/m/music.youtube.com or youtu.be"
    )

    if not url or url.startswith("-") or any(
        ch.isspace() or ord(ch) < 32 for ch in url
    ):
        raise HTTPException(status_code=400, detail=error)

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise HTTPException(status_code=400, detail=error)

    if (
        parts.scheme.lower() != "https"
        or (parts.hostname or "").lower() not in YOUTUBE_URL_HOSTS
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
    ):
        raise HTTPException(status_code=400, detail=error)

    return url

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
def media_token(request: Request):
    """Read-only per-user token for <img>/<video> src URLs (see AUTH above)."""
    user = current_user(request)
    with get_db() as conn:
        return auth.issue_media_token(conn, user["id"])


# ---------- accounts (P1.5) ----------

class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


def client_ip(request: Request) -> Optional[str]:
    # nginx is the only way in from outside (backend binds 127.0.0.1 + the compose net).
    fwd = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else ""
    return ip or (request.client.host if request.client else None)


def _set_session_cookie(request: Request, response: JSONResponse, token: str) -> None:
    secure = (
        request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    )
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_TTL_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request):
    username = payload.username.strip().lower()
    ip = client_ip(request)
    with get_db() as conn:
        if auth.login_blocked(conn, username, ip):
            raise HTTPException(
                status_code=429,
                detail="Too many failed logins. Try again in 15 minutes.",
                headers={"Retry-After": str(auth.LOGIN_WINDOW_MINUTES * 60)},
            )
        user = auth.authenticate(conn, username, payload.password)
        if not user:
            auth.record_login_failure(conn, username, ip)
            conn.commit()
            raise HTTPException(status_code=401, detail="Wrong username or password")
        auth.clear_login_failures(conn, username)
        token = auth.create_session(conn, user["id"], ip, request.headers.get("user-agent"))
        conn.commit()
    must_change = bool(user.pop("must_change_password", False))
    response = JSONResponse({"user": user, "must_change_password": must_change})
    _set_session_cookie(request, response, token)
    return response


@app.post("/api/auth/logout")
def logout(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE, "")
    if token:
        with get_db() as conn:
            auth.delete_session(conn, token)
            conn.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response


@app.get("/api/auth/me")
def auth_me(request: Request):
    user = current_user(request)
    return {
        "user": {k: user[k] for k in ("id", "username", "role")},
        "via": user["via"],
        "must_change_password": bool(user.get("must_change_password")),
    }


# ---------- API tokens (part 4): per user, for scripts ----------
# Managed from a signed-in browser session only, never by a token
# itself, so a leaked token can't mint or list others.

def _token_manager(request: Request) -> dict:
    user = current_user(request)
    if user["via"] != "session":
        raise HTTPException(status_code=403, detail="Manage API tokens from a signed-in browser")
    return user


@app.get("/api/auth/tokens")
def list_tokens(request: Request):
    user = _token_manager(request)
    with get_db() as conn:
        return {"tokens": auth.list_api_tokens(conn, user["id"])}


@app.post("/api/auth/tokens")
def create_token(payload: TokenCreate, request: Request):
    user = _token_manager(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give the token a name")
    with get_db() as conn:
        try:
            token = auth.create_api_token(conn, user["id"], name)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        conn.commit()
    return token


@app.delete("/api/auth/tokens/{token_id}")
def revoke_token(token_id: str, request: Request):
    user = _token_manager(request)
    with get_db() as conn:
        if not auth.delete_api_token(conn, user["id"], token_id):
            raise HTTPException(status_code=404, detail="Token not found")
        conn.commit()
    return {"ok": True}


# ---------- user admin (part 5): admins only (middleware 403s /api/admin/* for members) ----------
# No public signup: accounts exist only through POST /api/admin/users. A created or
# reset account gets a temporary password and must choose its own at next login.
# There is always at least one active admin (create can't, disable/demote can't remove it).

class AdminUserCreate(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)
    role: str = "member"


class AdminUserUpdate(BaseModel):
    active: Optional[bool] = None
    role: Optional[str] = None


class AdminPasswordReset(BaseModel):
    password: str = Field(max_length=256)


@app.get("/api/admin/users")
def admin_list_users(request: Request):
    require_admin(request)
    with get_db() as conn:
        return {"users": auth.list_users(conn)}


@app.post("/api/admin/users")
def admin_create_user(payload: AdminUserCreate, request: Request):
    require_admin(request)
    username = payload.username.strip().lower()
    problem = (
        auth.username_problem(username)
        or auth.password_problem(payload.password)
        or (None if payload.role in auth.ROLES else "Role must be admin or member")
    )
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    uid = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, username, password_hash, role, active, must_change_password)
                VALUES (%s, %s, %s, %s, TRUE, TRUE)
                ON CONFLICT (username) DO NOTHING
                RETURNING id
                """,
                (uid, username, auth.hash_password(payload.password), payload.role),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=409, detail=f"Username '{username}' is taken")
        conn.commit()
    print(f"[auth] user '{username}' ({payload.role}) created by an admin")
    return {"id": uid, "username": username, "role": payload.role, "active": True,
            "must_change_password": True}


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, request: Request):
    me = require_admin(request)
    if payload.role is not None and payload.role not in auth.ROLES:
        raise HTTPException(status_code=400, detail="Role must be admin or member")
    with get_db() as conn:
        with conn.cursor() as cur:
            target, admins = auth.locked_user_and_admins(cur, user_id)
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            _, username, role, active = target
            new_role = payload.role if payload.role is not None else role
            new_active = payload.active if payload.active is not None else active
            if user_id in admins and (new_role != "admin" or not new_active) and len(admins) <= 1:
                who = "yourself" if user_id == me["id"] else f"'{username}'"
                raise HTTPException(
                    status_code=409,
                    detail=f"Can't disable or demote {who}: the last active admin. Make another admin first.",
                )
            cur.execute(
                "UPDATE users SET role = %s, active = %s WHERE id = %s",
                (new_role, new_active, user_id),
            )
            if active and not new_active:
                # Disabling ends every session and deletes every API token.
                auth.end_user_access(cur, user_id, tokens=True)
        conn.commit()
    print(f"[auth] user '{username}' updated by an admin: role={new_role} active={new_active}")
    return {"id": user_id, "username": username, "role": new_role, "active": bool(new_active)}


@app.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, payload: AdminPasswordReset, request: Request):
    require_admin(request)
    problem = auth.password_problem(payload.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users SET password_hash = %s, password_changed_at = NOW(),
                                 must_change_password = TRUE
                WHERE id = %s RETURNING username
                """,
                (auth.hash_password(payload.password), user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            # Signed out everywhere; API tokens are kept (revoke them separately, or disable).
            auth.end_user_access(cur, user_id, tokens=False)
            auth.clear_login_failures(conn, row[0])
        conn.commit()
    print(f"[auth] password of '{row[0]}' reset by an admin")
    return {"ok": True, "must_change_password": True}


@app.post("/api/auth/password")
def change_password(payload: PasswordChange, request: Request):
    user = current_user(request)
    problem = auth.password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    with get_db() as conn:
        if not auth.authenticate(conn, user["username"], payload.current_password):
            raise HTTPException(status_code=400, detail="Current password is wrong")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s, password_changed_at=NOW(),"
                " must_change_password=FALSE WHERE id=%s",
                (auth.hash_password(payload.new_password), user["id"]),
            )
        # Every other session of this user ends; this browser stays logged in.
        auth.delete_user_sessions(conn, user["id"], keep_token=request.cookies.get(auth.SESSION_COOKIE))
        conn.commit()
    return {"ok": True}


# ============================================================
# CREATE JOB
# ============================================================

def percent_setting(key: str, fallback: float, lo: float, hi: float, user_id: Optional[str] = None) -> float:
    try:
        value = float(runtime_setting(key, user_id=user_id))
    except (TypeError, ValueError):
        value = fallback
    return max(lo, min(hi, value))


def disk_status() -> dict:
    usage = shutil.disk_usage(DATA_ROOT)
    try:
        min_mb = int(float(runtime_setting("DISK_SPACE_MIN_MB")))
    except (TypeError, ValueError):
        min_mb = 2048
    free_mb = usage.free // (1024 * 1024)
    return {
        "free_mb": free_mb,
        "total_mb": usage.total // (1024 * 1024),
        "min_mb": min_mb,
        "ok": free_mb >= min_mb,
    }


@app.get("/api/system/disk")
def get_disk_status():
    """Free space on DATA_ROOT for the Settings sheet (R-14)."""
    return disk_status()


@app.post("/api/jobs")
def create_job(req: ClipRequest, request: Request):
    user = current_user(request)

    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail="platform must be youtube_shorts, tiktok, or instagram_reels",
        )

    if req.layout is None:
        req.layout = campaigns.default_layout(campaigns.get(req.campaign)) if req.campaign else "auto"
    if req.layout not in SUPPORTED_LAYOUTS:
        raise HTTPException(
            status_code=400,
            detail="layout must be auto, left, right, or none",
        )
    if req.language is None:
        configured = (runtime_setting("WHISPER_LANGUAGE") or "").strip().lower()
        req.language = configured if configured in languages.REQUESTABLE else languages.DEFAULT
    if req.language not in languages.REQUESTABLE:
        raise HTTPException(
            status_code=400,
            detail="language must be auto, en, or id",
        )
    if req.language_fallback not in (None,) + languages.SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail="language_fallback must be en or id",
        )
    rules = None
    if req.campaign:
        rules = campaigns.get(req.campaign)
        if not rules:
            raise HTTPException(status_code=400, detail="Unknown campaign")
    wm = campaign_watermark_snapshot(rules)
    req.youtube_url = validate_youtube_url(req.youtube_url)

    # R-14: refuse up front instead of failing deep in the pipeline.
    # The exact per-video size check needs yt-dlp, so it runs in the
    # worker before the download (long work stays out of handlers).
    disk = disk_status()
    if not disk["ok"]:
        raise HTTPException(
            status_code=507,
            detail=(
                f"Not enough disk space to start a job: {disk['free_mb']} MB "
                f"free, the reserve is {disk['min_mb']} MB "
                "(DISK_SPACE_MIN_MB). Delete old jobs or free space."
            ),
        )

    # DEFAULT_SUBTITLE_* settings apply only to fields the client
    # didn't send (the Import form omits them on purpose).
    sent = req.model_fields_set

    style = normalize_subtitle_style(
        req.subtitle_style
        if "subtitle_style" in sent
        else {"style": runtime_setting("DEFAULT_SUBTITLE_STYLE", user_id=user["id"])},
        req.subtitle_font
        if "subtitle_font" in sent
        else runtime_setting("DEFAULT_SUBTITLE_FONT", user_id=user["id"]),
        req.subtitle_size
        if "subtitle_size" in sent
        else _settings.get_int("DEFAULT_SUBTITLE_SIZE", user_id=user["id"]),
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
                        subtitle_animation,
                        watermark_position_y,
                        subtitle_seam_gap,
                        language,
                        language_fallback,
                        campaign,
                        watermark_asset_id,
                        watermark_width,
                        watermark_opacity,
                        watermark_failure,
                        user_id
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
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
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
                        # R-17: freeze today's defaults onto the job so a
                        # later settings change doesn't move its layout.
                        # Pre-P1 #5: same 16-85 % range the Settings PUT allows (098); the
                        # worker never places it above 16 % anyway (078).
                        min(85.0, max(16.0, float(wm["position_y"])))
                        if wm.get("position_y") is not None
                        else percent_setting("WATERMARK_POSITION_Y", 25.0, 16, 85, user["id"]),
                        percent_setting("SUBTITLE_SEAM_GAP", 1.5, 0, 20, user["id"]),
                        req.language,
                        req.language_fallback,
                        req.campaign,
                        wm.get("asset_id"),
                        wm.get("width"),
                        wm.get("opacity"),
                        wm.get("failure"),
                        user["id"],
                    ),
                )

                job_id = cur.fetchone()[0]

            conn.commit()

        return {
            "id": str(job_id),
            "job_id": str(job_id),
            "status": "queued",
            "subtitle_style": style,
            # Pre-P1 #1: e.g. the campaign watermark isn't in the library.
            "warnings": [wm["failure"]] if wm.get("failure") else [],
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

# ============================================================
# ACTIVITY (090): everything running right now, in the one shape the
# frontend's job island reads: {kind, id, job_id, candidate_id,
# stage, percent, label, title, updated_at}. Every new background
# task kind (brief parsing, auto-import, publish kit, view pulling,
# auto-posting) adds its rows HERE instead of a new progress UI.
# ============================================================

CANDIDATE_BUSY = (
    "queued", "preview_queued", "preview_rendering", "render_queued",
    "rendering", "thumbnail_queued", "thumbnail_rendering",
)
SUBMAGIC_BUSY = (
    "queued_upload", "uploading", "transcribing", "queued_export",
    "exporting", "queued_apply", "applying",
)
# Pre-P1 #4: an ALLOW-list of running job states (an unknown/new status shows
# nothing rather than a phantom task). Mirrors index.html BUSY + "processing".
JOB_RUNNING = (
    "queued", "reanalyze_queued", "processing", "downloading", "download", "transcribing",
    "transcription", "transcribed", "analyzing", "analysis",
)


# ============================================================
# POSTING ACCOUNTS (P2 part 1, 128) — the caller's own accounts per
# platform, used by "Mark posted" (clip_posts, part 2) and the per-account
# monthly caps (part 4). Owned rows: the middleware guard 404s other users'.
# ============================================================

ACCOUNT_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class AccountCreate(BaseModel):
    platform: str = Field(max_length=20)
    handle: str = Field(max_length=80)
    note: Optional[str] = Field(default=None, max_length=120)


class AccountUpdate(BaseModel):
    handle: Optional[str] = Field(default=None, max_length=80)
    note: Optional[str] = Field(default=None, max_length=120)
    active: Optional[bool] = None


def _clean_handle(raw: str) -> str:
    handle = (raw or "").strip().lstrip("@").strip()
    if not ACCOUNT_HANDLE_RE.match(handle):
        raise HTTPException(
            status_code=400,
            detail="Handle: 1-64 letters, digits, '.', '_' or '-' (without spaces; a leading @ is fine)",
        )
    return handle


def _account_row(r) -> dict:
    return {
        "id": r[0], "platform": r[1], "platform_name": rule_checks.PLATFORM_LIMITS.get(r[1], (0, 0, r[1]))[2],
        "handle": r[2], "note": r[3], "active": bool(r[4]),
        "created_at": r[5].isoformat() if r[5] else None,
    }


ACCOUNT_COLUMNS = "id, platform, handle, note, active, created_at"


@app.get("/api/accounts")
def list_accounts(request: Request):
    user = current_user(request)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {ACCOUNT_COLUMNS} FROM platform_accounts WHERE user_id = %s "
                "ORDER BY platform, lower(handle)",
                (user["id"],),
            )
            rows = cur.fetchall()
    return {
        "accounts": [_account_row(r) for r in rows],
        "platforms": [{"slug": k, "name": v[2]} for k, v in rule_checks.PLATFORM_LIMITS.items()],
    }


@app.post("/api/accounts")
def create_account(payload: AccountCreate, request: Request):
    user = current_user(request)
    platform = payload.platform.strip().lower()
    if platform not in rule_checks.PLATFORM_LIMITS:
        raise HTTPException(status_code=400, detail=f"Unknown platform {platform!r}")
    handle = _clean_handle(payload.handle)
    note = (payload.note or "").strip() or None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO platform_accounts (id, user_id, platform, handle, note)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING {ACCOUNT_COLUMNS}
                """,
                (str(uuid.uuid4()), user["id"], platform, handle, note),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail=f"You already have @{handle} on this platform")
        conn.commit()
    return _account_row(row)


@app.patch("/api/accounts/{account_id}")
def update_account(account_id: str, payload: AccountUpdate, request: Request):
    user = current_user(request)
    sets, args = [], []
    if payload.handle is not None:
        sets.append("handle = %s"); args.append(_clean_handle(payload.handle))
    if payload.note is not None:
        sets.append("note = %s"); args.append(payload.note.strip() or None)
    if payload.active is not None:
        sets.append("active = %s"); args.append(payload.active)
    if not sets:
        raise HTTPException(status_code=400, detail="Nothing to change")
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"UPDATE platform_accounts SET {', '.join(sets)} WHERE id = %s AND user_id = %s "
                    f"RETURNING {ACCOUNT_COLUMNS}",
                    (*args, account_id, user["id"]),
                )
            except psycopg.errors.UniqueViolation:
                raise HTTPException(status_code=409, detail="You already have that handle on this platform")
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
        conn.commit()
    return _account_row(row)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str, request: Request):
    # An account with posts is paused instead of deleted, so post history keeps its account.
    user = current_user(request)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM clip_posts WHERE account_id = %s", (account_id,))
            used = cur.fetchone()[0]
            if used:
                cur.execute(
                    "UPDATE platform_accounts SET active = FALSE WHERE id = %s AND user_id = %s",
                    (account_id, user["id"]),
                )
                conn.commit()
                return {"ok": True, "paused": True,
                        "detail": f"Paused instead of removed: {used} post{'s' if used != 1 else ''} use this account"}
            cur.execute(
                "DELETE FROM platform_accounts WHERE id = %s AND user_id = %s",
                (account_id, user["id"]),
            )
            if not cur.rowcount:
                raise HTTPException(status_code=404, detail="Account not found")
        conn.commit()
    return {"ok": True}


# ============================================================
# CLIP POSTS (P2 part 2, 129) — rules in shared/posts.py; owned rows
# (POST_PATH_RE guard). Part 3's "Ready to post" and "Mark posted" write here.
# ============================================================

POST_COLUMNS = (
    "p.id, p.candidate_id, p.job_id, p.campaign, p.title, p.platform, p.account_id, a.handle, p.status, "
    "p.source, p.scheduled_for, p.posted_at, p.url, p.external_id, p.views, p.views_at, p.claimed_at, "
    "p.paid_at, p.paid_rp, p.note, p.error, p.created_at, p.updated_at"
)
POST_FROM = "clip_posts p LEFT JOIN platform_accounts a ON a.id = p.account_id"


def _post_row(r) -> dict:
    keys = ("id", "candidate_id", "job_id", "campaign", "title", "platform", "account_id", "account_handle",
            "status", "source", "scheduled_for", "posted_at", "url", "external_id", "views", "views_at",
            "claimed_at", "paid_at", "paid_rp", "note", "error", "created_at", "updated_at")
    d = dict(zip(keys, r))
    for k in ("scheduled_for", "posted_at", "views_at", "claimed_at", "paid_at", "created_at", "updated_at"):
        d[k] = d[k].isoformat() if d[k] else None
    return d


def _fetch_post(cur, post_id: str, user_id: str) -> dict:
    cur.execute(f"SELECT {POST_COLUMNS} FROM {POST_FROM} WHERE p.id = %s AND p.user_id = %s", (post_id, user_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    return _post_row(row)


def _check_account(cur, user_id: str, account_id: Optional[str], platform: str) -> None:
    if not account_id:
        return
    cur.execute(
        "SELECT platform, active FROM platform_accounts WHERE id = %s AND user_id = %s",
        (account_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    if row[0] != platform:
        raise HTTPException(status_code=400, detail="That account is on another platform")
    if not row[1]:
        raise HTTPException(status_code=400, detail="That account is paused")


def _parse_ts(value, field: str):
    if value in (None, ""):
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field}: use an ISO date-time")
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class PostCreate(BaseModel):
    candidate_id: str = Field(max_length=64)
    platform: str = Field(max_length=20)
    account_id: Optional[str] = Field(default=None, max_length=64)
    status: str = "planned"
    url: Optional[str] = Field(default=None, max_length=500)
    posted_at: Optional[str] = None
    scheduled_for: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)


class PostUpdate(BaseModel):
    status: Optional[str] = None
    account_id: Optional[str] = Field(default=None, max_length=64)
    url: Optional[str] = Field(default=None, max_length=500)
    posted_at: Optional[str] = None
    scheduled_for: Optional[str] = None
    views: Optional[int] = Field(default=None, ge=0)
    paid_rp: Optional[int] = None
    external_id: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=500)


def _complete_problem(post: dict) -> Optional[str]:
    missing = [f for f in post_rules.needs(post["status"]) if not post.get(f)]
    if missing:
        names = {"account_id": "the account", "url": "the post link", "posted_at": "when it was posted"}
        return f"A {post['status']} post needs " + " and ".join(names[m] for m in missing)
    return None


@app.get("/api/posts")
def list_posts(
    request: Request,
    status: Optional[str] = None,
    campaign: Optional[str] = None,
    candidate_id: Optional[str] = None,
    job_id: Optional[str] = None,
):
    user = current_user(request)
    where, args = ["p.user_id = %s"], [user["id"]]
    for col, val in (("p.status", status), ("p.campaign", campaign), ("p.candidate_id", candidate_id), ("p.job_id", job_id)):
        if val:
            where.append(f"{col} = %s"); args.append(val)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {POST_COLUMNS} FROM {POST_FROM} WHERE {' AND '.join(where)} "
                "ORDER BY p.created_at DESC LIMIT 500",
                args,
            )
            return {"posts": [_post_row(r) for r in cur.fetchall()]}


@app.post("/api/posts")
def create_post(payload: PostCreate, request: Request):
    user = current_user(request)
    platform = payload.platform.strip().lower()
    if platform not in rule_checks.PLATFORM_LIMITS:
        raise HTTPException(status_code=400, detail=f"Unknown platform {platform!r}")
    if payload.status not in ("planned", "posted"):
        raise HTTPException(status_code=400, detail="A new post is planned or posted")
    url = (payload.url or "").strip() or None
    problem = post_rules.url_problem(platform, url)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    posted_at = _parse_ts(payload.posted_at, "posted_at")
    if payload.status == "posted" and not posted_at:
        posted_at = datetime.now(timezone.utc)
    with get_db() as conn:
        with conn.cursor() as cur:
            # The clip must be the caller's (via its job) — another user's clip is 404.
            cur.execute(
                """
                SELECT c.job_id, j.campaign,
                       COALESCE(NULLIF(c.manual_title, ''), NULLIF(c.title, ''), c.ai_title)
                FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
                WHERE c.id = %s AND j.user_id = %s
                """,
                (payload.candidate_id, user["id"]),
            )
            clip = cur.fetchone()
            if not clip:
                raise HTTPException(status_code=404, detail="Clip not found")
            _check_account(cur, user["id"], payload.account_id, platform)
            post = {"status": payload.status, "account_id": payload.account_id, "url": url, "posted_at": posted_at}
            problem = _complete_problem(post)
            if problem:
                raise HTTPException(status_code=400, detail=problem)
            pid = str(uuid.uuid4())
            try:
                cur.execute(
                    """
                    INSERT INTO clip_posts (id, user_id, candidate_id, job_id, campaign, title, platform, account_id,
                                            status, scheduled_for, posted_at, url, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (pid, user["id"], payload.candidate_id, clip[0], clip[1], clip[2], platform,
                     payload.account_id, payload.status, _parse_ts(payload.scheduled_for, "scheduled_for"),
                     posted_at, url, (payload.note or "").strip() or None),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise HTTPException(
                    status_code=409,
                    detail="That link is already recorded" if "uq_clip_posts_url" in str(exc)
                    else "This clip already has a post on that account (drop it first to re-post)",
                )
            post = _fetch_post(cur, pid, user["id"])
        conn.commit()
    return post


@app.patch("/api/posts/{post_id}")
def update_post(post_id: str, payload: PostUpdate, request: Request):
    user = current_user(request)
    sent = payload.model_fields_set
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM clip_posts WHERE id = %s AND user_id = %s FOR UPDATE", (post_id, user["id"]))
            current = _fetch_post(cur, post_id, user["id"])
            new = dict(current)
            sets = {}
            if "status" in sent and payload.status is not None:
                problem = post_rules.transition_problem(current["status"], payload.status)
                if problem:
                    raise HTTPException(status_code=409, detail=problem)
                if payload.status != current["status"]:
                    sets["status"] = new["status"] = payload.status
                    if payload.status == "posted" and not new["posted_at"] and "posted_at" not in sent:
                        sets["posted_at"] = new["posted_at"] = datetime.now(timezone.utc)
                    if payload.status == "claimed":
                        sets["claimed_at"] = datetime.now(timezone.utc)
                    if payload.status == "paid":
                        sets["paid_at"] = datetime.now(timezone.utc)
            if "account_id" in sent:
                _check_account(cur, user["id"], payload.account_id, current["platform"])
                sets["account_id"] = new["account_id"] = payload.account_id
            if "url" in sent:
                url = (payload.url or "").strip() or None
                problem = post_rules.url_problem(current["platform"], url)
                if problem:
                    raise HTTPException(status_code=400, detail=problem)
                sets["url"] = new["url"] = url
            if "posted_at" in sent:
                sets["posted_at"] = new["posted_at"] = _parse_ts(payload.posted_at, "posted_at")
            if "scheduled_for" in sent:
                sets["scheduled_for"] = _parse_ts(payload.scheduled_for, "scheduled_for")
            if "views" in sent and payload.views is not None:
                sets["views"] = payload.views
                sets["views_at"] = datetime.now(timezone.utc)  # every views entry is stamped
            if "paid_rp" in sent:
                problem = post_rules.rp_problem(payload.paid_rp)
                if problem:
                    raise HTTPException(status_code=400, detail=problem)
                sets["paid_rp"] = new["paid_rp"] = payload.paid_rp
            if "external_id" in sent:
                sets["external_id"] = (payload.external_id or "").strip() or None
            if "note" in sent:
                sets["note"] = (payload.note or "").strip() or None
            problem = _complete_problem(new)
            if problem:
                raise HTTPException(status_code=400, detail=problem)
            if new["status"] == "paid" and new.get("paid_rp") is None:
                raise HTTPException(status_code=400, detail="A paid post needs the amount (paid_rp, Rupiah)")
            if sets:
                cols = ", ".join(f"{k} = %s" for k in sets)
                try:
                    cur.execute(
                        f"UPDATE clip_posts SET {cols}, updated_at = NOW() WHERE id = %s AND user_id = %s",
                        (*sets.values(), post_id, user["id"]),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise HTTPException(
                        status_code=409,
                        detail="That link is already recorded" if "uq_clip_posts_url" in str(exc)
                        else "This clip already has a post on that account",
                    )
            post = _fetch_post(cur, post_id, user["id"])
        conn.commit()
    return post


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: str, request: Request):
    """Only planned or dropped rows can be deleted; anything posted is history (drop it instead)."""
    user = current_user(request)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM clip_posts WHERE id = %s AND user_id = %s AND status IN ('planned', 'dropped') "
                "RETURNING id",
                (post_id, user["id"]),
            )
            if not cur.fetchone():
                cur.execute("SELECT status FROM clip_posts WHERE id = %s AND user_id = %s", (post_id, user["id"]))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Post not found")
                raise HTTPException(status_code=409, detail=f"A {row[0]} post is history: drop it instead of deleting")
        conn.commit()
    return {"ok": True}


# Analyze form: "≈ 6 min for a 1 h 24 min video" from the caller's own finished jobs
# (P1.5 scope). Video length = end of the last transcript segment; processing =
# started_at → review_ready_at (queue wait excluded). samples 0 = no history (UI hides it).
@app.get("/api/analysis-estimate")
def analysis_estimate(request: Request):
    user = current_user(request)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXTRACT(EPOCH FROM review_ready_at - started_at),
                       (transcript_segments -> -1 ->> 'end')::float
                FROM jobs
                WHERE user_id = %s AND review_ready_at IS NOT NULL AND started_at IS NOT NULL
                  AND review_ready_at > started_at
                  AND jsonb_typeof(transcript_segments) = 'array'
                  AND jsonb_array_length(transcript_segments) > 0
                ORDER BY review_ready_at DESC
                LIMIT 20
                """,
                (user["id"],),
            )
            rows = [(float(p), float(v)) for p, v in cur.fetchall() if p and v and v >= 60]
    if not rows:
        return {"samples": 0}
    rate = statistics.median(p / v for p, v in rows)
    video = statistics.median(v for _, v in rows)
    return {
        "samples": len(rows),
        "video_seconds": round(video),
        "processing_seconds": round(rate * video),
        "seconds_per_video_minute": round(rate * 60, 1),
    }


@app.get("/api/activity")
def list_activity(request: Request):
    # P1.5: own tasks only; admin sees everyone's (rows of other users carry "owner").
    user = current_user(request)
    see_all = user["role"] == "admin"
    items = []
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.id, j.status, j.progress, j.message,
                       COALESCE(NULLIF(j.custom_title, ''), sv.title), j.updated_at,
                       NULLIF(u.username, %s)
                FROM jobs j LEFT JOIN source_videos sv ON sv.id = j.source_video_id
                JOIN users u ON u.id = j.user_id
                WHERE j.status = ANY(%s) AND (%s OR j.user_id = %s)
                ORDER BY j.created_at
                """,
                (user["username"], list(JOB_RUNNING), see_all, user["id"]),
            )
            for jid, status, progress, message, title, upd, owner in cur.fetchall():
                items.append({"owner": owner,
                    "kind": "job", "id": str(jid), "job_id": str(jid), "candidate_id": None,
                    "stage": status, "percent": int(progress or 0), "label": message or status,
                    "title": title, "updated_at": upd.isoformat() if upd else None,
                })
            cur.execute(
                """
                SELECT c.id, c.job_id, c.status, c.progress, c.message,
                       c.submagic_status,
                       COALESCE(NULLIF(c.manual_title, ''), NULLIF(c.title, ''), c.ai_title),
                       c.updated_at, NULLIF(u.username, %s)
                FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
                JOIN users u ON u.id = j.user_id
                WHERE (c.status = ANY(%s) OR c.submagic_status = ANY(%s))
                  AND j.status IS DISTINCT FROM 'cancelled'
                  AND (%s OR j.user_id = %s)
                ORDER BY c.updated_at
                """,
                (user["username"], list(CANDIDATE_BUSY), list(SUBMAGIC_BUSY), see_all, user["id"]),
            )
            for cid, jid, status, progress, message, sm, title, upd, owner in cur.fetchall():
                base = {"owner": owner, "id": str(cid), "job_id": str(jid), "candidate_id": str(cid),
                        "title": title, "updated_at": upd.isoformat() if upd else None}
                if status in CANDIDATE_BUSY:
                    items.append({**base, "kind": "candidate", "stage": status,
                                  "percent": int(progress or 0), "label": message or status})
                if sm in SUBMAGIC_BUSY:
                    # Submagic reports no percentage: indeterminate (percent None),
                    # "processing" once it runs (pre-P1 #4: no fake 50 %).
                    items.append({**base, "kind": "submagic", "stage": sm, "percent": None,
                                  "label": "Submagic: queued" if sm.startswith("queued") else "Submagic: processing"})
    return {"items": items}


@app.get("/api/jobs")
def list_jobs(
    request: Request,
    scope: str = "current",
):
    user = current_user(request)

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
                        j.subtitle_animation,
                        j.watermark_width,
                        j.watermark_opacity,
                        j.burn_subtitles,
                        j.attempts,
                        j.error_class,
                        j.retry_after,
                        j.watermark_position_y,
                        j.subtitle_seam_gap,
                        j.language,
                        j.detected_language,
                        j.language_confidence,
                        j.effective_language,
                        j.campaign
                    FROM jobs j
                    LEFT JOIN source_videos sv
                        ON sv.id = j.source_video_id
                    WHERE {status_filter} AND j.user_id = %s
                    ORDER BY j.created_at DESC
                    """

                cur.execute(query, (user["id"],))

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
                        j.subtitle_animation,
                        j.watermark_width,
                        j.watermark_opacity,
                        j.burn_subtitles,
                        j.attempts,
                        j.error_class,
                        j.retry_after,
                        j.watermark_position_y,
                        j.subtitle_seam_gap,
                        j.language,
                        j.detected_language,
                        j.language_confidence,
                        j.effective_language,
                        j.campaign
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

        # 109 (P1): campaign rule chips per clip (same function as the approve gate).
        rules = campaigns.get(job.get("campaign")) if job.get("campaign") else None
        for cand in job["candidates"]:
            cand["rule_checks"] = rule_checks.check(rules, cand)

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

        if req.edit_spec is not None:
            try:
                merge, remove = edit_specs.normalize_patch(
                    req.edit_spec, SUBTITLE_STYLE_PRESETS, SUBTITLE_ANIMATIONS
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            fields.append(
                "edit_spec = NULLIF((COALESCE(edit_spec, '{}'::jsonb) || %s::jsonb)"
                " - %s::text[], '{}'::jsonb)"
            )
            values.extend([json_param(merge), remove])

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

@app.patch("/api/jobs/{job_id}/render-options")
def update_render_options(job_id: str, req: RenderOptionsUpdate):
    """Job-level render options shared by every candidate of the job
    (R-05 watermark, R-09 burn_subtitles). Takes effect on the next
    preview/final render."""

    fields = sorted(req.model_fields_set)

    with get_db() as conn:

        with conn.cursor() as cur:

            if fields:
                cur.execute(
                    "UPDATE jobs SET "
                    + ", ".join(f"{name} = %s" for name in fields)
                    + " WHERE id = %s RETURNING id",
                    [getattr(req, name) for name in fields] + [job_id],
                )
            else:
                cur.execute(
                    "SELECT id FROM jobs WHERE id = %s", (job_id,),
                )

            if not cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail="Job not found",
                )

            if fields:
                mark_finals_outdated(cur, job_id)  # 114

        conn.commit()

    return {"ok": True, "updated": fields}


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

                # 114: finals go stale only when the job style really changes
                # (Apply re-sends the unchanged job values on every clip edit).
                cur.execute(
                    "SELECT subtitle_style, subtitle_font, subtitle_size, subtitle_animation FROM jobs WHERE id = %s",
                    (job_id,),
                )
                before = cur.fetchone()
                changed = before is not None and (
                    (before[0] or {}).get("style") != style.get("style")
                    or (before[1] or None) != style["font"]
                    or (before[2] or None) != style["size"]
                    or (before[3] or None) != style["animation"]
                )

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

                if changed:
                    mark_finals_outdated(cur, job_id)

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
                mark_finals_outdated(cur, job_id, candidate_id)

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
# CAPTION PRESET → ALL CLIPS (083): the preset becomes the job's
# style/animation, every clip's own caption override is cleared, and
# clips sitting in review get their preview re-rendered.
# ============================================================

@app.post("/api/jobs/{job_id}/caption-preset")
def apply_caption_preset_to_all(job_id: str, req: CaptionPresetAll):

    try:
        cap = edit_specs.normalize_caption(
            req.model_dump(), SUBTITLE_STYLE_PRESETS, SUBTITLE_ANIMATIONS
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subtitle_style, subtitle_font, subtitle_size FROM jobs WHERE id = %s FOR UPDATE",
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")

            current = row[0] if isinstance(row[0], dict) else {}
            style = normalize_subtitle_style(
                {**current, "style": cap["style"], "animation": cap["animation"]},
                row[1], row[2], cap["animation"],
            )
            cur.execute(
                """
                UPDATE jobs
                SET subtitle_style = %s::jsonb, subtitle_animation = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (json_param(style), style["animation"], job_id),
            )
            cur.execute(
                """
                UPDATE clip_candidates
                SET edit_spec = NULLIF(edit_spec - 'caption', '{}'::jsonb), updated_at = NOW()
                WHERE job_id = %s AND edit_spec ? 'caption'
                """,
                (job_id,),
            )
            cur.execute(
                """
                UPDATE clip_candidates
                SET status = 'preview_queued', progress = 0,
                    message = 'Queued: caption preset applied to all clips',
                    error_stage = NULL, error_message = NULL, updated_at = NOW()
                WHERE job_id = %s AND status = 'review'
                RETURNING id
                """,
                (job_id,),
            )
            queued = [r[0] for r in cur.fetchall()]
            for cid in queued:
                record_candidate_version(cur, cid, "Caption preset applied to all clips")
            mark_finals_outdated(cur, job_id)
        conn.commit()

    return {"status": "updated", "subtitle_style": style, "queued": queued}


FINAL_OUTDATED_MSG = "Final outdated · re-render"


def mark_finals_outdated(cur, job_id: str, candidate_id: str = None) -> int:
    """114 (QA Low on 108): a render-affecting change on a clip that already has a
    final marks that final outdated (render warning "final_outdated" → chip). The
    worker clears it when a new final completes. candidate_id=None = every clip of
    the job (job-level changes). Same cursor/transaction as the change."""
    entry = json_param([{"code": "final_outdated", "message": FINAL_OUTDATED_MSG,
                         "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}])
    cur.execute(
        """
        UPDATE clip_candidates
        SET render_warnings = COALESCE((SELECT jsonb_agg(x) FROM jsonb_array_elements(
                COALESCE(render_warnings, '[]'::jsonb)) x WHERE x->>'code' <> 'final_outdated'),
                '[]'::jsonb) || %s::jsonb
        WHERE job_id = %s AND final_path IS NOT NULL AND (%s::text IS NULL OR id::text = %s::text)
        """,
        (entry, job_id, candidate_id, candidate_id),
    )
    return cur.rowcount


def candidate_rule_failures(job_id: str, candidate_id: str) -> list:
    """109: blocking rule chips that fail for this clip ([] = no campaign / all pass)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.*, j.campaign AS _campaign FROM clip_candidates c JOIN jobs j ON j.id = c.job_id "
                "WHERE c.id = %s AND c.job_id = %s",
                (candidate_id, job_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Candidate not found")
            cand = dict(zip([d.name for d in cur.description], row))
    rules = campaigns.get(cand["_campaign"]) if cand.get("_campaign") else None
    return rule_checks.blocking_failures(rule_checks.check(rules, cand))


class RuleFix(BaseModel):
    rule: str  # "hashtags" | "dismiss"


@app.post("/api/jobs/{job_id}/candidates/{candidate_id}/fix-rule")
def fix_candidate_rule(job_id: str, candidate_id: str, req: RuleFix):
    """109: one-click fixes for rule chips. hashtags → the description ends with the
    campaign hashtags in order (081 helper); dismiss → the content-safety warning is
    acknowledged (the user decides; the flags stay recorded)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.description, c.safety_check, j.campaign FROM clip_candidates c "
                "JOIN jobs j ON j.id = c.job_id WHERE c.id = %s AND c.job_id = %s",
                (candidate_id, job_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Candidate not found")
            description, safety, slug = row
            rules = campaigns.get(slug) if slug else None
            if req.rule == "hashtags":
                if not rules:
                    raise HTTPException(status_code=400, detail="Not a campaign clip")
                cur.execute(
                    "UPDATE clip_candidates SET description = %s, updated_at = NOW() WHERE id = %s",
                    (with_campaign_hashtags(description or "", rules), candidate_id),
                )
            elif req.rule == "dismiss":
                if not isinstance(safety, dict):
                    raise HTTPException(status_code=400, detail="No content check to dismiss")
                cur.execute(
                    "UPDATE clip_candidates SET safety_check = safety_check || %s::jsonb, updated_at = NOW() WHERE id = %s",
                    (json_param({"dismissed": True}), candidate_id),
                )
            else:
                raise HTTPException(status_code=400, detail="Unknown rule fix")
        conn.commit()
    return {"status": "fixed", "rule": req.rule}


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

        # 109 (P1): campaign clips approve only when every blocking rule passes.
        failing = candidate_rule_failures(job_id, candidate_id)
        if failing:
            raise HTTPException(
                status_code=409,
                detail=f"Fix {len(failing)} rule{'s' if len(failing) != 1 else ''} to approve: "
                       + "; ".join(ch["label"] for ch in failing),
            )

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


def _load_user_settings(user_id: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM user_settings WHERE user_id = %s", (user_id,))
            return {row[0]: row[1] for row in cur.fetchall()}


_settings = RuntimeSettings(
    _load_app_settings,
    log=lambda msg: print("[backend]", msg),
    user_loader=_load_user_settings,
)


def runtime_setting(
    key: str,
    fallback: str | None = None,
    user_id: str | None = None,
) -> str | None:
    """
    Same rule as the worker's setting(): app_settings (DB) wins,
    then env, then fallback / DEFAULT_SETTINGS. 5 s cache; PUT
    /api/settings invalidates it. Env-only keys (DATABASE_URL, CORS_ALLOWED_ORIGINS, admin bootstrap)
    never come from the DB.
    """
    # P1.5: pass user_id for USER_SETTING_KEYS (user → global → default).
    return _settings.get(key, fallback, user_id)


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
            f"(short, engaging, in {languages.name(job_language_of(job_id))}), "
            f"and 'reason' (short string).\n\n"
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
                        -- 110: the new-hook prompt has no score (no prompt change);
                        -- clear the old hook's so the UI shows no stale estimate.
                        score = NULL,
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

DESCRIPTION_SCHEMA = descriptions.DESCRIPTION_SCHEMA


def campaign_watermark_snapshot(rules) -> dict:
    """081: the campaign's watermark preset as job columns: asset id (by id,
    else by filename stem = asset name), width, opacity, centre y %. {} =
    no campaign / no preset: the job keeps the global settings."""
    preset = campaigns.watermark(rules) if rules else None
    if not preset:
        return {}
    asset_id, failure = None, None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if preset["asset_id"]:
                    cur.execute(
                        # Campaigns are a shared, admin-managed catalogue (P1.5):
                        # their watermark is an admin's asset, never a member's.
                        "SELECT id FROM watermark_assets WHERE id::text = %s"
                        " AND user_id IN (SELECT id FROM users WHERE role = 'admin')",
                        (str(preset["asset_id"]),),
                    )
                    row = cur.fetchone()
                    asset_id = str(row[0]) if row else None
                if not asset_id and preset["asset_name"]:
                    cur.execute(
                        "SELECT id FROM watermark_assets WHERE lower(regexp_replace("
                        "filename, '\\.[^.]+$', '')) = lower(%s) "
                        "AND user_id IN (SELECT id FROM users WHERE role = 'admin') "
                        "ORDER BY created_at DESC LIMIT 1",
                        (preset["asset_name"],),
                    )
                    row = cur.fetchone()
                    asset_id = str(row[0]) if row else None
    except Exception as exc:
        print(f"Campaign watermark lookup failed: {exc}")
        failure = f"Campaign watermark lookup failed: {exc}"[:300]
    if not asset_id:
        # Pre-P1 #1: never fall back to the active watermark. The failure is
        # stored on the job; every render goes without a watermark + chip.
        failure = failure or (
            f"Campaign watermark {preset['asset_name'] or preset['asset_id']!r} "
            "isn't in the watermark library"
        )
        print(f"Campaign {rules['slug']}: {failure}; clips render WITHOUT a watermark")
    return {
        "failure": failure,
        "asset_id": asset_id,
        "width": preset["width"],
        "opacity": preset["opacity"],
        "position_y": preset["center_y_pct"],
    }


def job_campaign_of(job_id: str):
    """The job's campaign rules dict, or None."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT campaign FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
    except Exception:
        row = None
    return campaigns.get(row[0]) if row and row[0] else None


HASHTAG_RE = re.compile(r"(?<![\w&])#[\w]+", re.UNICODE)


def with_campaign_hashtags(text: str, rules) -> str:
    """081: campaign hashtags at the END, exact order (shared since 115)."""
    return campaigns.with_campaign_hashtags(text, rules)


@app.get("/api/campaigns")
def list_campaigns():
    """Campaigns from docs/campaigns/*.rules.json (re-read on change)."""
    return [campaigns.summary(r) for r in campaigns.load_all().values()]


def job_language_of(job_id: str) -> str:
    """'en' or 'id' for this job (079): what its prompts are written for."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT effective_language, language FROM jobs WHERE id = %s",
                    (job_id,),
                )
                row = cur.fetchone()
    except Exception:
        row = None
    return languages.job_language(*(row or (None, None)))


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
            f"The text below is an {languages.name(job_language_of(job_id))} subtitle for a "
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
def generate_description(job_id: str, candidate_id: str, request: Request):
    owner_id = current_user(request)["id"]

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

        hashtags = runtime_setting("HASHTAGS", "", user_id=owner_id) or ""
        campaign = runtime_setting("CAMPAIGN_NAME", "") or ""

        lang = job_language_of(job_id)
        lang_name = languages.name(lang)
        rules = job_campaign_of(job_id)
        if rules:
            # The campaign's own tags are appended after generation (exact order).
            hashtags, campaign = "", ""

        prompt = descriptions.build_description_prompt(
            platform=platform, content_type=content_type, title=title, subtitle=subtitle,
            lang=lang, lang_name=lang_name, rules=rules, hashtags=hashtags, campaign=campaign,
        )
        data = ai_generate_json(
            prompt, DESCRIPTION_SCHEMA, task="description",
            max_tokens=1024,
        )
        description = str(data.get("description", "")).strip()
        if rules and description:
            description = with_campaign_hashtags(description, rules)

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

# Decompression-bomb guard for both image uploads (audit-001 F5):
# 40 MP is ~5x a 4K frame, far above any real thumbnail/watermark.
UPLOAD_MAX_PIXELS = 40_000_000


def reencode_uploaded_image(raw, fmt):
    """Decode an upload with Pillow and return freshly encoded bytes.

    Anything Pillow can't open/verify (SVG, HTML, truncated files) or
    whose pixel count exceeds UPLOAD_MAX_PIXELS is rejected with a 400;
    the raw upload bytes are never written to disk.
    """
    import io
    import warnings

    from PIL import Image

    # Pillow's own bomb check (warning > limit, error > 2x) is armed
    # at our limit too, so it fires before any pixel data is decoded.
    Image.MAX_IMAGE_PIXELS = UPLOAD_MAX_PIXELS

    invalid = HTTPException(
        status_code=400,
        detail="Uploaded file is not a readable image (PNG, JPEG, WebP or GIF)",
    )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(io.BytesIO(raw)) as probe:
                width, height = probe.size
                if width * height > UPLOAD_MAX_PIXELS:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Image is too large ({width}x{height}); "
                            f"max {UPLOAD_MAX_PIXELS // 1_000_000} megapixels"
                        ),
                    )
                probe.verify()

            # verify() leaves the image unusable; decode a fresh copy.
            with Image.open(io.BytesIO(raw)) as img:
                img.load()
                if fmt == "PNG":
                    out_img = img.convert("RGBA")
                    save_kwargs = {}
                else:
                    out_img = img.convert("RGB")
                    save_kwargs = {"quality": 92}

        buf = io.BytesIO()
        out_img.save(buf, fmt, **save_kwargs)
        return buf.getvalue(), out_img.size

    except HTTPException:
        raise

    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(
            status_code=400,
            detail=(
                "Image is too large; max "
                f"{UPLOAD_MAX_PIXELS // 1_000_000} megapixels"
            ),
        )

    except Exception:
        raise invalid


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

        # Decode + re-encode before touching the DB; rejects non-images.
        jpeg_bytes, _ = reencode_uploaded_image(raw, "JPEG")

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

        # Always the re-encoded JPEG (matching every other thumbnail
        # option), never the client's bytes.
        out_path.write_bytes(jpeg_bytes)

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
def list_watermark_assets(request: Request):
    user = current_user(request)

    try:

        active_id = runtime_setting("ACTIVE_WATERMARK_ID", user_id=user["id"]) or ""

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename, width, height, created_at
                    FROM watermark_assets
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user["id"],),
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
async def upload_watermark_asset(request: Request, file: UploadFile = File(...)):
    user = current_user(request)

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

        # PNG keeps alpha transparency, which matters for a watermark
        # overlay. Rejects anything Pillow can't decode.
        png_bytes, (width, height) = reencode_uploaded_image(raw, "PNG")

        asset_id = str(uuid.uuid4())
        wm_dir = DATA_ROOT / "watermarks"
        wm_dir.mkdir(parents=True, exist_ok=True)
        out_path = wm_dir / f"{asset_id}.png"

        out_path.write_bytes(png_bytes)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO watermark_assets
                        (id, filename, path, width, height, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        asset_id,
                        file.filename or "watermark.png",
                        str(out_path.relative_to(DATA_ROOT)),
                        width,
                        height,
                        user["id"],
                    ),
                )

                # First asset ever uploaded becomes active automatically
                # — otherwise uploading would silently do nothing until
                # the user also remembers to activate it.
                cur.execute(
                    "SELECT COUNT(*) FROM watermark_assets WHERE user_id = %s",
                    (user["id"],),
                )
                count = cur.fetchone()[0]

                if count == 1:
                    set_user_setting(cur, user["id"], "ACTIVE_WATERMARK_ID", asset_id)

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
def activate_watermark_asset(asset_id: str, request: Request):
    user = current_user(request)

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

                set_user_setting(cur, user["id"], "ACTIVE_WATERMARK_ID", asset_id)

            conn.commit()

        _settings.invalidate()
        return {"status": "ok", "active_id": asset_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/assets/watermarks/{asset_id}")
def delete_watermark_asset(asset_id: str, request: Request):
    user = current_user(request)

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

                active_id = runtime_setting("ACTIVE_WATERMARK_ID", user_id=user["id"]) or ""
                if active_id == asset_id:
                    set_user_setting(cur, user["id"], "ACTIVE_WATERMARK_ID", None)

            conn.commit()

        _settings.invalidate()
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
                c.edit_spec,
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
            "edit_spec": row[5],
            "subtitle_style": row[6],
            "subtitle_font": row[7],
            "subtitle_size": row[8],
            "subtitle_animation": row[9],
            "layout": row[10],
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
                        -- 083: per-clip edits are the candidate's own; pre-083
                        -- snapshots have no key and keep the current spec.
                        edit_spec = CASE WHEN %s THEN %s::jsonb ELSE edit_spec END,
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
                        "edit_spec" in snapshot,
                        json_param(snapshot.get("edit_spec")) if snapshot.get("edit_spec") else None,
                        str(version),
                        candidate_id,
                        job_id,
                    ),
                )

                if not cur.fetchone():
                    raise HTTPException(
                        status_code=404, detail="Candidate not found"
                    )

                mark_finals_outdated(cur, job_id, candidate_id)  # 114

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

        # 113 (QA Medium on 109): adopting the Submagic render is a final too —
        # same campaign rule gate as Approve.
        failing = candidate_rule_failures(job_id, candidate_id)
        if failing:
            raise HTTPException(
                status_code=409,
                detail=f"Fix {len(failing)} rule{'s' if len(failing) != 1 else ''} to approve: "
                       + "; ".join(ch["label"] for ch in failing),
            )

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
def get_settings(request: Request):
    # P1.5: members get only the user-level keys (their own effective
    # values); admins get everything. scope = user|global tells the UI
    # where a save goes (user_settings vs app_settings).
    user = current_user(request)
    is_admin = user["role"] == "admin"
    try:
        # Effective value (user -> DB -> env -> default), i.e. what the
        # worker will actually use for this user's jobs, plus its source.
        _settings.invalidate()
        result = {}

        for key in DEFAULT_SETTINGS:
            scope = "user" if key in USER_SETTING_KEYS else "global"
            if scope == "global" and not is_admin:
                continue
            value, source = _settings.resolve(key, user_id=user["id"])
            if key in SECRET_SETTING_KEYS and value:
                result[key] = {
                    "value": "••••••••",
                    "configured": True,
                    "source": source,
                    "scope": scope,
                }
            else:
                result[key] = {
                    "value": value,
                    "configured": bool(value),
                    "source": source,
                    "scope": scope,
                }

        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


HOOKS_WINDOW_MIN_MINUTES = 10


def validate_watermark_height(values: dict):
    """P0 cleanup: the worker never places the watermark above 16 % (078), so
    the setting can't ask for it (5-15 % used to be accepted, then clamped)."""
    v = str(values.get("WATERMARK_POSITION_Y") or "").strip()
    if not v:
        return
    try:
        y = float(v)
    except ValueError:
        raise HTTPException(status_code=400, detail="Watermark height must be a number (% from top)")
    if not 16 <= y <= 85:
        raise HTTPException(status_code=400, detail="Watermark height must be between 16 and 85 % from the top "
                                                    "(platform UI covers the top 16 %)")


def validate_hooks_windows(values: dict):
    """QA #4: overlap must stay below the window (else the worker never
    advances); checked against the values this PUT would leave effective."""
    keys = ("HOOKS_WINDOW_MINUTES", "HOOKS_WINDOW_OVERLAP_MINUTES")
    if not any(k in values for k in keys):
        return
    eff = {}
    for k in keys:
        if k in values:
            v = str(values[k] or "").strip()
            # empty = unset: falls through to env, then the default
            eff[k] = v or os.getenv(k) or DEFAULT_SETTINGS[k]
        else:
            eff[k] = runtime_setting(k)
    try:
        window, overlap = (float(eff[k]) for k in keys)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Hook window settings must be numbers (minutes)")
    if window < HOOKS_WINDOW_MIN_MINUTES:
        # P0: a 1-minute window = 120-240 AI calls for a 2-hour video.
        raise HTTPException(
            status_code=400,
            detail=f"Hook analysis window must be at least {HOOKS_WINDOW_MIN_MINUTES} minutes "
                   f"(smaller windows multiply AI calls)",
        )
    if overlap < 0 or overlap >= window:
        raise HTTPException(
            status_code=400,
            detail=f"Hook window overlap ({overlap:g} min) must be at least 0 and less than "
                   f"the window ({window:g} min)",
        )


@app.put("/api/settings")
def update_settings(req: SettingsUpdate, request: Request):
    user = current_user(request)
    unknown = [k for k in req.values if k not in DEFAULT_SETTINGS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting key(s): {unknown}",
        )
    global_keys = [k for k in req.values if k not in USER_SETTING_KEYS]
    if global_keys and user["role"] != "admin":
        # P1.5: global settings (AI keys, Whisper, disk, …) are admin-only.
        raise HTTPException(
            status_code=403,
            detail=f"Only an admin can change global settings: {global_keys}",
        )
    if "ACTIVE_WATERMARK_ID" in req.values and str(req.values["ACTIVE_WATERMARK_ID"] or "").strip():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM watermark_assets WHERE id::text = %s AND user_id = %s",
                    (str(req.values["ACTIVE_WATERMARK_ID"]).strip(), user["id"]),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Watermark asset not found")

    validate_hooks_windows(req.values)
    validate_watermark_height(req.values)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for key, value in req.values.items():
                    if value == "••••••••":
                        continue
                    if key in USER_SETTING_KEYS:
                        # The caller's own value (admin too); "" = back to the global default.
                        set_user_setting(cur, user["id"], key, value)
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

# ============================================================
# CANCEL JOB (R-08)
# ============================================================
# Sets the job and its in-flight candidates to 'cancelled'. The worker
# notices within ~2 s (CancelWatch polls the DB), terminates the running
# ffmpeg/yt-dlp and stops at the next stage boundary; its update_job()/
# update_candidate() never overwrite a cancelled row, and the claims skip
# cancelled jobs. Candidates already in review/completed are untouched,
# and Submagic work already at Submagic (transcribing/exporting) is left
# to finish: an export may already be billed.

JOB_NOT_CANCELLABLE = (
    "completed", "failed", "cancelled", "paused", "review",
    "partial_failure",
)

CANDIDATE_BUSY_STATUSES = (
    "queued", "preview_queued", "preview_rendering", "render_queued",
    "rendering", "thumbnail_queued", "thumbnail_rendering",
)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):

    with get_db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                "SELECT status FROM jobs WHERE id = %s FOR UPDATE",
                (job_id,),
            )

            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Job not found")

            if row[0] in JOB_NOT_CANCELLABLE:
                raise HTTPException(
                    status_code=409,
                    detail=f"Job is {row[0]}; only running jobs can be cancelled",
                )

            cur.execute(
                """
                UPDATE jobs
                SET status = 'cancelled',
                    message = 'Cancelled by user',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (job_id,),
            )

            cur.execute(
                """
                UPDATE clip_candidates
                SET status = 'cancelled',
                    message = 'Cancelled by user',
                    updated_at = NOW()
                WHERE job_id = %s
                  AND status = ANY(%s)
                """,
                (job_id, list(CANDIDATE_BUSY_STATUSES)),
            )

            cancelled_candidates = cur.rowcount

            cur.execute(
                """
                UPDATE clip_candidates
                SET submagic_status = 'failed',
                    submagic_error = 'Cancelled with the job',
                    updated_at = NOW()
                WHERE job_id = %s
                  AND submagic_status IN (
                      'queued_upload', 'queued_export', 'queued_apply'
                  )
                """,
                (job_id,),
            )

        conn.commit()

    return {
        "status": "cancelled",
        "job_id": job_id,
        "cancelled_candidates": cancelled_candidates,
    }


# ============================================================
# RETRY (R-15)
# ============================================================
# Manual retry of a failed job or candidate: resets the attempt
# counter and error, keeps every edit and the version history. A job
# with a stored transcript (and a source that retention hasn't purged)
# re-runs only the analysis; otherwise it starts over from download.
# A candidate goes back to the queue it failed in (error_stage holds
# the queued status it was claimed from).

CANDIDATE_RETRY_QUEUES = ("preview_queued", "render_queued", "thumbnail_queued")


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):

    with get_db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT j.status,
                       j.transcript IS NOT NULL,
                       sv.source_path IS NOT NULL
                FROM jobs j
                LEFT JOIN source_videos sv ON sv.id = j.source_video_id
                WHERE j.id = %s
                FOR UPDATE OF j
                """,
                (job_id,),
            )

            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Job not found")

            if row[0] != "failed":
                raise HTTPException(
                    status_code=409,
                    detail=f"Job is {row[0]}; only failed jobs can be retried",
                )

            status = "reanalyze_queued" if row[1] and row[2] else "queued"

            cur.execute(
                """
                UPDATE jobs
                SET status = %s,
                    message = 'Queued: retry requested',
                    attempts = 0,
                    error_class = NULL,
                    error_stage = NULL,
                    error_message = NULL,
                    retry_after = NULL,
                    completed_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, job_id),
            )

        conn.commit()

    return {"status": status, "job_id": job_id}


@app.post("/api/jobs/{job_id}/candidates/{candidate_id}/retry")
def retry_candidate(job_id: str, candidate_id: str):

    with get_db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT c.status, c.error_stage, j.status
                FROM clip_candidates c
                JOIN jobs j ON j.id = c.job_id
                WHERE c.id = %s AND c.job_id = %s
                FOR UPDATE OF c
                """,
                (candidate_id, job_id),
            )

            row = cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail="Candidate not found",
                )

            if row[0] != "failed":
                raise HTTPException(
                    status_code=409,
                    detail=f"Candidate is {row[0]}; only failed candidates can be retried",
                )

            if row[2] == "cancelled":
                raise HTTPException(
                    status_code=409,
                    detail="The job was cancelled; retry the job instead",
                )

            status = (
                row[1] if row[1] in CANDIDATE_RETRY_QUEUES
                else "preview_queued"
            )

            cur.execute(
                """
                UPDATE clip_candidates
                SET status = %s,
                    progress = 0,
                    message = 'Queued: retry requested',
                    attempts = 0,
                    error_class = NULL,
                    error_stage = NULL,
                    error_message = NULL,
                    retry_after = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, candidate_id),
            )

        conn.commit()

    return {"status": status, "candidate_id": candidate_id}


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
                # across jobs. (There is no transcripts table on the
                # rebuilt schema.) Its download/audio/normalized files
                # are left to the worker's retention/orphan sweeps (R-14).
                # candidate_versions has no FK cascade: delete explicitly.
                # ------------------------------------------------

                cur.execute(
                    """
                    DELETE FROM candidate_versions
                    WHERE candidate_id IN (
                        SELECT id FROM clip_candidates WHERE job_id = %s
                    )
                    """,
                    (job_id,),
                )

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