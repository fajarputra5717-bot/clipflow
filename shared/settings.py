"""
Runtime settings: ONE precedence rule for backend (main.py) and
worker (worker.py). Both files build a RuntimeSettings with their
own DB loader and call .get() through their thin wrappers
(`runtime_setting()` in main.py, `setting()` in worker.py).

Precedence, first non-empty wins:
    1. app_settings table (edited in the UI)
    2. process environment (.env)
    3. explicit default passed by the caller, else DEFAULT_SETTINGS

The DB is read at most once per CACHE_TTL_SECONDS per process, so a
UI change reaches the worker within ~5 s without a restart.

ENV_ONLY_KEYS are never read from the DB even if a row exists:
app_settings is served over the API, so auth material must not live
there (see R-03).
"""

import os
import threading
import time


CACHE_TTL_SECONDS = 5.0

# Whitelist for PUT /api/settings AND the single source of defaults.
# A key that isn't here can't be saved from the UI.
DEFAULT_SETTINGS = {
    "GEMINI_ANALYSIS_MODEL": "gemini-3.6-flash",
    "GEMINI_MAX_ATTEMPTS": "4",
    # faster-whisper model name (R-07): tiny|base|small|medium|large-v3.
    # medium int8 on CPU ≈ the old openai-whisper base speed.
    "WHISPER_MODEL": "medium",
    "WHISPER_LANGUAGE": "id",
    "CLIPS_PER_JOB": "4",  # 136: per user, 1–8; snapshotted on jobs.clip_count (replaces CLIP_COUNT)
    "CLIP_TARGET_DURATION": "35",
    "CLIP_MIN_DURATION": "20",
    "CLIP_MAX_DURATION": "55",
    # Hook analysis input (076): the whole timed transcript up to this many
    # characters; longer ones go in windows (+ overlap) and a final ranking call.
    "HOOKS_FULL_TRANSCRIPT_MAX_CHARS": "400000",
    "HOOKS_WINDOW_MINUTES": "30",
    "HOOKS_WINDOW_OVERLAP_MINUTES": "2",
    "FACE_DETECTION_SAMPLE_COUNT": "16",
    "FACE_CONFIDENCE_THRESHOLD": "0.60",
    # Face height / crop height. 0.78 = face fills more of the bottom
    # pane (R-04; baseline was 0.62).
    "FACE_ZOOM_RATIO": "0.78",
    "PREVIEW_WIDTH": "540",
    "FFMPEG_PREVIEW_PRESET": "ultrafast",
    "FFMPEG_PREVIEW_CRF": "30",
    "FFMPEG_PRESET": "veryfast",
    "FFMPEG_CRF": "23",
    # Width of the VISIBLE mark (PNG cropped to its alpha bbox) on a
    # 1080-wide video. R-16: 320, as on the old VM; the baseline's 630
    # scaled the whole (often full-canvas) PNG instead.
    "WATERMARK_WIDTH": "320",
    "WATERMARK_OPACITY": "1.0",
    # R-17 default positions, copied onto each NEW job at creation
    # (jobs.watermark_position_y / subtitle_seam_gap). Older jobs have
    # NULL there and keep the legacy 50 % / 4 %.
    # Centre of the watermark, % of video height from the top.
    "WATERMARK_POSITION_Y": "25",
    # Gap between the caption's bottom and the facecam seam, % of height
    # (floored at 2x the caption outline so it never crosses the seam).
    "SUBTITLE_SEAM_GAP": "1.5",
    # Full-frame clips (no facecam panel): caption anchor, % of height from the
    # top (bottom of the caption block sits the seam gap above it); clamped
    # 60-85 by the worker to stay above the platforms' bottom UI.
    "FULLFRAME_CAPTION_Y": "78",
    "DEFAULT_SUBTITLE_STYLE": "outline",
    "DEFAULT_SUBTITLE_FONT": "Liberation Sans Bold",
    "DEFAULT_SUBTITLE_SIZE": "42",
    "HASHTAGS": "",
    "CAMPAIGN_NAME": "",
    "GEMINI_API_KEY": "",
    # Claude (R-21). Model IDs live only here; check them against
    # Anthropic's model list when bumping.
    "ANTHROPIC_API_KEY": "",
    # Failover policy (R-22): gemini | claude | auto (Gemini first,
    # Claude on transient errors). See shared/ai/router.py.
    "CLIP_ANALYSIS_PROVIDER": "auto",
    "TEXT_UTILITY_PROVIDER": "auto",
    "CLAUDE_MODEL_ANALYSIS": "claude-sonnet-5-5",
    "CLAUDE_MODEL_UTILITY": "claude-haiku-4-5",
    "RUNWAY_API_KEY": "",
    "RUNWAY_MODEL": "gen4_image_turbo",
    "YOUTUBE_CLIENT_ID": "",
    "YOUTUBE_CLIENT_SECRET": "",
    "YOUTUBE_REFRESH_TOKEN": "",
    # TIKTOK_* / INSTAGRAM_* have no consumer yet (no publisher code
    # in the baseline); kept so the UI fields stay saveable.
    "TIKTOK_CLIENT_KEY": "",
    "TIKTOK_CLIENT_SECRET": "",
    "TIKTOK_ACCESS_TOKEN": "",
    "INSTAGRAM_ACCESS_TOKEN": "",
    "INSTAGRAM_BUSINESS_ACCOUNT_ID": "",
    "SUBMAGIC_API_KEY": "",
    "SUBMAGIC_TEMPLATE": "Hormozi 2",
    "SUBMAGIC_MAGIC_ZOOMS": "true",
    "SUBMAGIC_MAGIC_BROLLS": "true",
    "ACTIVE_WATERMARK_ID": "",
    # Disk retention + guards (R-14).
    "RETENTION_DAYS_INTERMEDIATE": "3",
    "ORPHAN_SWEEP_DRY_RUN": "true",
    "DISK_SPACE_MIN_MB": "2048",
    # Failure recovery (R-15): automatic retries of transient failures
    # and of work orphaned by a worker restart, per job/candidate.
    "JOB_MAX_ATTEMPTS": "3",
    "STALE_CLAIM_MINUTES": "5",
}

SECRET_SETTING_KEYS = {
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "RUNWAY_API_KEY",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_ACCESS_TOKEN",
    "INSTAGRAM_ACCESS_TOKEN",
    "SUBMAGIC_API_KEY",
}

ENV_ONLY_KEYS = {
    "CLIPFLOW_ADMIN_USER",
    "CLIPFLOW_ADMIN_PASSWORD",
    "CLIPFLOW_ENV",
    "CORS_ALLOWED_ORIGINS",
    "DATABASE_URL",
}


# P1.5: user-level keys. Each user may override them (user_settings table);
# precedence for these: user → app_settings (admin's house default) → env →
# DEFAULT_SETTINGS. Everything else is global and admin-only to change.
USER_SETTING_KEYS = {
    "CLIPS_PER_JOB",
    "DEFAULT_SUBTITLE_STYLE",
    "DEFAULT_SUBTITLE_FONT",
    "DEFAULT_SUBTITLE_SIZE",
    "FULLFRAME_CAPTION_Y",
    "SUBTITLE_SEAM_GAP",
    "WATERMARK_WIDTH",
    "WATERMARK_OPACITY",
    "WATERMARK_POSITION_Y",
    "ACTIVE_WATERMARK_ID",
    "HASHTAGS",
}

# User-level keys with NO global fallback: the value names a row the user
# owns (a watermark asset), so another user's value must never apply.
USER_ONLY_KEYS = {"ACTIVE_WATERMARK_ID"}


def _present(value):
    return value is not None and str(value).strip() != ""


class RuntimeSettings:

    def __init__(self, loader, log=print, user_loader=None):
        # loader() -> {key: value} from app_settings; may raise.
        # user_loader(user_id) -> {key: value} from user_settings (P1.5).
        self._loader = loader
        self._user_loader = user_loader
        self._log = log
        self._lock = threading.Lock()
        self._rows = {}
        self._loaded_at = None
        self._user_rows = {}  # user_id -> (loaded_at, rows)

    def invalidate(self):
        with self._lock:
            self._loaded_at = None
            self._user_rows = {}

    def _rows_for_user(self, user_id):
        if not user_id or not self._user_loader:
            return {}
        with self._lock:
            now = time.monotonic()
            hit = self._user_rows.get(user_id)
            if hit and now - hit[0] < CACHE_TTL_SECONDS:
                return hit[1]
            rows = hit[1] if hit else {}
            try:
                rows = dict(self._user_loader(user_id) or {})
            except Exception as exc:
                self._log(f"Could not load user_settings for {user_id}: {exc}")
            self._user_rows[user_id] = (now, rows)
            return rows

    def _db_rows(self):
        with self._lock:
            now = time.monotonic()
            if (
                self._loaded_at is not None
                and now - self._loaded_at < CACHE_TTL_SECONDS
            ):
                return self._rows
            try:
                self._rows = dict(self._loader() or {})
            except Exception as exc:
                # Keep the last good snapshot; retry after the TTL
                # instead of hammering a DB that's down.
                self._log(f"Could not load app_settings: {exc}")
            self._loaded_at = now
            return self._rows

    def resolve(self, key, default=None, user_id=None):
        """(value, source) with source in user|db|env|default. user_id only
        matters for USER_SETTING_KEYS; USER_ONLY_KEYS never fall back to
        the global value when a user is given."""
        if user_id and key in USER_SETTING_KEYS:
            value = self._rows_for_user(user_id).get(key)
            if _present(value):
                return str(value), "user"
            if key in USER_ONLY_KEYS:
                return (default if default is not None else DEFAULT_SETTINGS.get(key)), "default"
        if key not in ENV_ONLY_KEYS:
            value = self._db_rows().get(key)
            if _present(value):
                return str(value), "db"
        value = os.getenv(key)
        if _present(value):
            return value, "env"
        if default is None:
            default = DEFAULT_SETTINGS.get(key)
        return default, "default"

    def get(self, key, default=None, user_id=None):
        return self.resolve(key, default, user_id)[0]

    def get_int(self, key, default=None, user_id=None):
        return int(self._number(key, default, int, user_id))

    def get_float(self, key, default=None, user_id=None):
        return float(self._number(key, default, float, user_id))

    def _number(self, key, default, cast, user_id=None):
        value = self.get(key, default, user_id)
        try:
            return cast(float(value)) if cast is int else cast(value)
        except (TypeError, ValueError):
            fallback = (
                default if default is not None
                else DEFAULT_SETTINGS[key]
            )
            self._log(
                f"Setting {key}={value!r} is not a number; "
                f"using {fallback}"
            )
            return cast(float(fallback)) if cast is int else cast(fallback)
