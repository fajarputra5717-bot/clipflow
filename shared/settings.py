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
    "WHISPER_MODEL": "base",
    "WHISPER_LANGUAGE": "id",
    "CLIP_COUNT": "2",
    "CLIP_TARGET_DURATION": "35",
    "CLIP_MIN_DURATION": "20",
    "CLIP_MAX_DURATION": "55",
    "FACE_DETECTION_SAMPLE_COUNT": "16",
    "FACE_CONFIDENCE_THRESHOLD": "0.60",
    "FACE_ZOOM_RATIO": "0.62",
    "PREVIEW_WIDTH": "540",
    "FFMPEG_PREVIEW_PRESET": "ultrafast",
    "FFMPEG_PREVIEW_CRF": "30",
    "FFMPEG_PRESET": "veryfast",
    "FFMPEG_CRF": "23",
    # 630 = what the worker actually rendered with in the baseline
    # (its code default); the old UI default of 480 was never used.
    # R-16 revisits this with the alpha-bbox geometry.
    "WATERMARK_WIDTH": "630",
    "WATERMARK_OPACITY": "1.0",
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
    "CLIPFLOW_API_KEY",
    "CORS_ALLOWED_ORIGINS",
    "DATABASE_URL",
}


def _present(value):
    return value is not None and str(value).strip() != ""


class RuntimeSettings:

    def __init__(self, loader, log=print):
        # loader() -> {key: value} from app_settings; may raise.
        self._loader = loader
        self._log = log
        self._lock = threading.Lock()
        self._rows = {}
        self._loaded_at = None

    def invalidate(self):
        with self._lock:
            self._loaded_at = None

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

    def resolve(self, key, default=None):
        """(value, source) with source in db|env|default."""
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

    def get(self, key, default=None):
        return self.resolve(key, default)[0]

    def get_int(self, key, default=None):
        return int(self._number(key, default, int))

    def get_float(self, key, default=None):
        return float(self._number(key, default, float))

    def _number(self, key, default, cast):
        value = self.get(key, default)
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
