import json
import os
import random
import re
import statistics
import subprocess
import time
import traceback
import uuid

import requests as _requests

from pathlib import Path

import cv2
import psycopg

from faster_whisper import WhisperModel
from psycopg.rows import dict_row

from shared.ai import router as ai_router
from shared.settings import RuntimeSettings


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_URL = os.environ["DATABASE_URL"]

DATA_ROOT = Path(
    os.getenv(
        "DATA_ROOT",
        "/data",
    )
)

DOWNLOAD_DIR = DATA_ROOT / "downloads"
AUDIO_DIR = DATA_ROOT / "audio"
SUBTITLE_DIR = DATA_ROOT / "subtitles"
PREVIEW_DIR = DATA_ROOT / "previews"
FINAL_DIR = DATA_ROOT / "final"
NORMALIZED_DIR = DATA_ROOT / "normalized"
THUMBNAIL_DIR = DATA_ROOT / "thumbnails"


for directory in [
    DOWNLOAD_DIR,
    AUDIO_DIR,
    SUBTITLE_DIR,
    PREVIEW_DIR,
    FINAL_DIR,
    NORMALIZED_DIR,
    THUMBNAIL_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# VIDEO SETTINGS
# ============================================================

FINAL_WIDTH = 1080
FINAL_HEIGHT = 1920

# PREVIEW_WIDTH, CLIP_COUNT, CLIP_*_DURATION, FACE_*, WATERMARK_*,
# FFMPEG_* are runtime settings: read them through setting_int() /
# setting_float() at use time, never as import-time constants (the
# baseline froze them from env, so the settings UI had no effect).


def preview_size():
    width = setting_int("PREVIEW_WIDTH")
    return width, int(width * 16 / 9)


# ============================================================
# FACE DETECTION
# ============================================================


FACE_MODEL_DIR = Path("/app/models")

FACE_PROTO_PATH = (
    FACE_MODEL_DIR
    / "deploy.prototxt"
)

FACE_MODEL_PATH = (
    FACE_MODEL_DIR
    / "res10_300x300_ssd_iter_140000.caffemodel"
)


# ============================================================
# WATERMARK
# ============================================================

WATERMARK_PATH = Path(
    "/app/assets/watermark.png"
)


def resolve_watermark_path():
    """
    The watermark burned into every render is chosen from the asset
    library (main.py's /api/assets/watermarks endpoints) rather than
    fixed at build time. Falls back to the baked-in default asset
    until something has been uploaded and activated.
    """

    active_id = setting("ACTIVE_WATERMARK_ID")

    if active_id:

        try:

            with db() as conn:

                row = conn.execute(
                    "SELECT path FROM watermark_assets WHERE id = %s",
                    (active_id,),
                ).fetchone()

            if row and row.get("path"):

                candidate = DATA_ROOT / row["path"]

                if candidate.exists():
                    return candidate

        except Exception as exc:

            log(
                "Could not resolve active watermark asset: "
                + str(exc)
            )

    return WATERMARK_PATH


def _watermark_pixel_size():
    """Natural (width, height) of the currently active watermark
    asset, or None if it can't be read. Used only to keep captions
    clear of the watermark's actual footprint instead of guessing its
    shape."""
    try:
        img = cv2.imread(str(resolve_watermark_path()))
        if img is None:
            return None
        h, w = img.shape[:2]
        return (w, h) if w and h else None
    except Exception:
        return None


# ============================================================
# GEMINI
# ============================================================

# IMPORTANT:
# This application intentionally uses ONLY Gemini 3.6 Flash.
GEMINI_MODEL = "gemini-3.6-flash"

CONTENT_TYPES = {
    "Funny",
    "Wise",
    "Reality",
    "Hype",
    "Wholesome",
    "Educational",
}

# Expected shape of analyze_hooks() output: a JSON array of clips.
HOOKS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "title": {"type": "string"},
            "reason": {"type": "string"},
            "score": {"type": "integer"},
            "content_type": {
                "type": "string",
                "enum": sorted(CONTENT_TYPES),
            },
            "rating": {"type": "integer"},
        },
        "required": [
            "start", "end", "title", "reason",
            "score", "content_type", "rating",
        ],
    },
}



# ============================================================
# SUBMAGIC (optional, opt-in per candidate — see main.py's
# /submagic/* endpoints for the user-facing side of this)
# ============================================================

SUBMAGIC_API_BASE = "https://api.submagic.co/v1"


def submagic_request(
    method,
    path,
    *,
    api_key,
    **kwargs,
):
    """
    Thin wrapper around requests for the Submagic API. Raises
    RuntimeError with a readable message on any non-2xx response
    instead of letting a raw requests exception surface.
    """

    url = SUBMAGIC_API_BASE + path

    headers = kwargs.pop("headers", {}) or {}
    headers["x-api-key"] = api_key

    resp = _requests.request(
        method,
        url,
        headers=headers,
        timeout=kwargs.pop("timeout", 120),
        **kwargs,
    )

    if resp.status_code >= 400:

        detail = resp.text[:500]

        try:
            detail = resp.json().get("message", detail)
        except Exception:
            pass

        raise RuntimeError(
            f"Submagic {method} {path} -> "
            f"HTTP {resp.status_code}: {detail}"
        )

    if not resp.text:
        return {}

    return resp.json()


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)


# ============================================================
# LOGGING
# ============================================================

def log(message):

    print(
        "[riftstorm-worker] "
        + str(message),
        flush=True,
    )


# ============================================================
# DATABASE
# ============================================================

def db():

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def load_app_settings():
    with db() as conn:
        rows = conn.execute(
            "SELECT key, value FROM app_settings"
        ).fetchall()
    return {row["key"]: row["value"] for row in rows}


# DB wins, then env, then DEFAULT_SETTINGS (shared/settings.py).
# Cached 5 s, so a UI change lands within one cache window.
_settings = RuntimeSettings(
    load_app_settings,
    log=lambda msg: log(msg),
)


def setting(name, default=None):
    return _settings.get(name, default)


def setting_int(name, default=None):
    return _settings.get_int(name, default)


def setting_float(name, default=None):
    return _settings.get_float(name, default)


# Every AI call goes through shared/ai/router.py (R-20).
ai_router.configure(setting, log)


def update_job(
    job_id,
    *,
    status=None,
    progress=None,
    message=None,
    error_stage=None,
    error=None,
):

    sets = []
    values = []

    mapping = {
        "status": status,
        "progress": progress,
        "message": message,
        "error_stage": error_stage,
        "error_message": error,
    }

    for column, value in mapping.items():

        if value is not None:

            sets.append(
                f"{column} = %s"
            )

            values.append(
                value
            )

    if not sets:
        return

    sets.append(
        "updated_at = NOW()"
    )

    values.append(
        job_id
    )

    with db() as conn:

        conn.execute(
            f"""
            UPDATE jobs
            SET {", ".join(sets)}
            WHERE id = %s
            """,
            values,
        )

        conn.commit()


def update_candidate(
    candidate_id,
    **fields
):

    if not fields:
        return

    sets = []
    values = []

    for key, value in fields.items():

        sets.append(
            f"{key} = %s"
        )

        values.append(
            value
        )

    sets.append(
        "updated_at = NOW()"
    )

    values.append(
        candidate_id
    )

    with db() as conn:

        conn.execute(
            f"""
            UPDATE clip_candidates
            SET {", ".join(sets)}
            WHERE id = %s
            """,
            values,
        )

        conn.commit()


# ============================================================
# PROCESS EXECUTION
# ============================================================

def run_command(
    command,
    *,
    check=True,
):

    log(
        "RUN: "
        + " ".join(
            map(str, command)
        )
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output = (
        result.stdout
        or ""
    )

    if check and result.returncode != 0:

        raise RuntimeError(
            output[-12000:]
        )

    return (
        result.returncode,
        output,
    )


# ============================================================
# FFPROBE
# ============================================================

def video_codec(video_path):

    try:

        _, output = run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
        )

        codec = (
            output.strip()
            .splitlines()
        )

        if codec:

            return codec[0].strip().lower()

    except Exception as exc:

        log(
            "ffprobe codec detection failed: "
            + str(exc)
        )

    return ""


# ============================================================
# AV1 NORMALIZATION
# ============================================================

def normalize_video(
    video_path,
    job_id,
):

    codec = video_codec(
        video_path
    )

    log(
        f"Source video codec: {codec or 'unknown'}"
    )

    # H.264 does not need normalization.
    if codec in {
        "h264",
        "avc1",
    }:

        return video_path

    # Only normalize AV1.
    if codec not in {
        "av1",
        "av01",
    }:

        log(
            "Video is not AV1; "
            "using original source"
        )

        return video_path

    normalized_path = (
        NORMALIZED_DIR
        / f"{job_id}_h264.mp4"
    )

    if normalized_path.exists():

        log(
            "Reusing normalized H.264 video: "
            + str(normalized_path)
        )

        return normalized_path

    log(
        "AV1 source detected."
    )

    log(
        "Normalizing AV1 -> H.264 using software decoding."
    )

    run_command(
        [
            "ffmpeg",
            "-y",

            # Explicitly disable hardware acceleration.
            "-hwaccel",
            "none",

            "-i",
            str(video_path),

            "-map",
            "0:v:0",

            "-map",
            "0:a?",

            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "20",

            "-pix_fmt",
            "yuv420p",

            "-c:a",
            "aac",

            "-b:a",
            "160k",

            "-movflags",
            "+faststart",

            str(normalized_path),
        ]
    )

    if not normalized_path.exists():

        raise RuntimeError(
            "AV1 normalization completed "
            "but H.264 output was not found"
        )

    log(
        "H.264 normalization complete: "
        + str(normalized_path)
    )

    return normalized_path


# ============================================================
# GEMINI
# ============================================================

def validate_ai():

    # R-22: fail only if NO provider can serve hook analysis.
    if not any(
        ai_router.PROVIDERS[name].is_configured(setting)
        for name in ai_router.AUTO_ORDER
    ):

        raise RuntimeError(
            "No AI provider configured "
            "(set GEMINI_API_KEY and/or ANTHROPIC_API_KEY)"
        )

    if "2.5" in GEMINI_MODEL.lower():

        raise RuntimeError(
            "Gemini 2.5 is explicitly forbidden"
        )

    if GEMINI_MODEL != "gemini-3.6-flash":

        raise RuntimeError(
            "Unsupported Gemini model. "
            "Required: gemini-3.6-flash"
        )


# ============================================================
# DOWNLOAD
# ============================================================

# R-07: the 1080x1920 render never needs more than 1080p, and an AV1
# stream forces normalize_video() to re-encode the whole file. Prefer
# H.264 <=1080p, then any codec <=1080p, then anything at all.
YTDLP_FORMAT = (
    "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]"
    "/bv*[height<=1080][vcodec^=avc1]+ba"
    "/bv*[height<=1080]+ba"
    "/b[height<=1080]"
    "/bv*+ba/b"
)


YTDLP_MAX_ATTEMPTS = 3

# yt-dlp output that means "try again later", not "this URL is bad":
# YouTube's intermittent 403s on media URLs, rate limits, 5xx, and
# network errors. A private/removed video fails the same way every time.
_TRANSIENT_DOWNLOAD_RE = re.compile(
    r"HTTP Error (403|408|429|5\d\d)"
    r"|timed out|Connection (reset|refused|aborted)"
    r"|Temporary failure in name resolution|Network is unreachable"
    r"|IncompleteRead|RemoteDisconnected|Read timed out"
    r"|Got error: .*(403|429|5\d\d)",
    re.IGNORECASE,
)


def is_transient_download_error(message):
    return bool(_TRANSIENT_DOWNLOAD_RE.search(message or ""))


def download_video(
    youtube_url,
    job_id,
):

    existing = list(
        DOWNLOAD_DIR.glob(
            f"{job_id}.*"
        )
    )

    for path in existing:

        if path.suffix.lower() in {
            ".mp4",
            ".mkv",
            ".webm",
            ".mov",
        }:

            log(
                "Reusing downloaded video: "
                + str(path)
            )

            return path

    template = str(
        DOWNLOAD_DIR
        / f"{job_id}.%(ext)s"
    )

    command = [
        "yt-dlp",

        "--no-playlist",

        "--merge-output-format",
        "mp4",

        "-f",
        YTDLP_FORMAT,

        "-o",
        template,

        # End of options: a URL starting with "-" can't be parsed
        # as a yt-dlp flag (security audit 060, option injection).
        "--",
        youtube_url,
    ]

    for attempt in range(1, YTDLP_MAX_ATTEMPTS + 1):

        try:

            run_command(command)

            break

        except RuntimeError as exc:

            if (
                attempt >= YTDLP_MAX_ATTEMPTS
                or not is_transient_download_error(str(exc))
            ):
                raise

            delay = 5 * 2 ** (attempt - 1) + random.uniform(0, 2)

            log(
                f"yt-dlp transient failure (attempt {attempt}/"
                f"{YTDLP_MAX_ATTEMPTS}), retrying in {delay:.0f}s: "
                + str(exc).strip().splitlines()[-1][:200]
            )

            time.sleep(delay)

    candidates = list(
        DOWNLOAD_DIR.glob(
            f"{job_id}.*"
        )
    )

    for path in candidates:

        if path.suffix.lower() in {
            ".mp4",
            ".mkv",
            ".webm",
            ".mov",
        }:

            return path

    raise RuntimeError(
        "Downloaded video not found"
    )


# ============================================================
# AUDIO
# ============================================================

def extract_audio(
    video_path,
    job_id,
):

    output = (
        AUDIO_DIR
        / f"{job_id}.mp3"
    )

    if output.exists():

        return output

    run_command(
        [
            "ffmpeg",
            "-y",

            "-hwaccel",
            "none",

            "-i",
            str(video_path),

            "-vn",

            "-ac",
            "1",

            "-ar",
            "16000",

            "-codec:a",
            "libmp3lame",

            "-q:a",
            "5",

            str(output),
        ]
    )

    return output


# ============================================================
# WHISPER
# ============================================================

# faster-whisper (CTranslate2) since R-07; was openai-whisper.
# WHISPER_MODEL / WHISPER_LANGUAGE are runtime settings (default
# medium / id). The model is cached per process and reloaded only when
# the WHISPER_MODEL setting changes.
WHISPER_COMPUTE_TYPE = "int8"

_whisper_model = None
_whisper_model_name = None


def whisper_model():

    global _whisper_model, _whisper_model_name

    name = setting("WHISPER_MODEL")

    if _whisper_model is None or name != _whisper_model_name:

        _whisper_model = None

        log(
            "Loading Whisper model: "
            + name
            + f" (faster-whisper, {WHISPER_COMPUTE_TYPE}, CPU)"
        )

        # Downloaded from the HF hub into HF_HOME on first use; that
        # path is the hf_cache volume, so rebuilds don't redownload.
        _whisper_model = WhisperModel(
            name,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
            cpu_threads=os.cpu_count() or 4,
        )

        _whisper_model_name = name

    return _whisper_model


def transcribe(
    audio_path
):

    log(
        "Transcribing audio locally"
    )

    raw_segments, _info = whisper_model().transcribe(
        str(audio_path),
        language=setting("WHISPER_LANGUAGE"),
        task="transcribe",
        word_timestamps=True,
    )

    # The generator does the actual decoding; materialize it once.
    raw_segments = list(raw_segments)

    transcript = "".join(
        segment.text for segment in raw_segments
    ).strip()

    segments = []

    for raw in raw_segments:

        # Same dict shape openai-whisper produced, so everything
        # downstream (jobs.transcript_segments, make_ass) is unchanged.
        segment = {
            "start": raw.start,
            "end": raw.end,
            "text": raw.text,
            "words": [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in (raw.words or [])
            ],
        }

        words = []

        for w in segment.get("words", []) or []:
            word_text = str(w.get("word", "")).strip()
            if not word_text:
                continue
            try:
                w_start = float(w.get("start", segment.get("start", 0)))
                w_end = float(w.get("end", w_start))
            except (TypeError, ValueError):
                continue
            if w_end <= w_start:
                w_end = w_start + 0.01
            words.append({
                "word": word_text,
                "start": w_start,
                "end": w_end,
            })

        segments.append(
            {
                "start": float(
                    segment.get(
                        "start",
                        0,
                    )
                ),

                "end": float(
                    segment.get(
                        "end",
                        0,
                    )
                ),

                "text": str(
                    segment.get(
                        "text",
                        "",
                    )
                ).strip(),

                # Per-word timing, used to light up each word as
                # it's spoken (karaoke-style captions). Empty when
                # Whisper couldn't align words for this segment —
                # rendering falls back to a plain static line.
                "words": words,
            }
        )

    return (
        transcript,
        segments,
    )


# ============================================================
# VIRAL HOOK ANALYSIS
# ============================================================

def analyze_hooks(
    transcript,
    segments,
    platform="youtube_shorts",
    clip_count=None,
):

    validate_ai()

    if not segments:

        raise RuntimeError(
            "No transcript segments available"
        )

    if clip_count is None:
        clip_count = setting_int("CLIP_COUNT")

    clip_target_duration = setting_int("CLIP_TARGET_DURATION")
    clip_min_duration = setting_int("CLIP_MIN_DURATION")
    clip_max_duration = setting_int("CLIP_MAX_DURATION")

    timed_transcript = "\n".join(
        (
            f"[{segment['start']:.1f}-"
            f"{segment['end']:.1f}] "
            f"{segment['text']}"
        )
        for segment in segments
    )

    timed_transcript = (
        timed_transcript[:24000]
    )

    prompt = f"""
You are an expert short-form gaming video editor.

Analyze the timestamped transcript and choose EXACTLY
{clip_count} DIFFERENT moments with the highest probability
of working as a {platform} short-form clip.

Important:
- Each clip must make sense by itself.
- Prefer strong reactions, funny moments, conflict,
  surprise, excitement, gameplay discoveries, impressive
  mechanics, or punchlines.
- Do not select boring setup.
- Avoid duplicate or overlapping moments.
- Target approximately {clip_target_duration} seconds.
- Minimum duration {clip_min_duration} seconds.
- Maximum duration {clip_max_duration} seconds.
- Keep start/end inside the transcript.
- Create an Indonesian title when the content is Indonesian.
- Title must be truthful and maximum 90 characters.

Additionally, classify each clip with exactly ONE content_type
from this fixed list: Funny, Wise, Reality, Hype, Wholesome,
Educational. Pick whichever best matches the moment's tone.

Also give a "rating" from 1 to 10 estimating how likely this
specific clip is to perform well as a standalone short, based on
hook strength, pacing, and shareability.

Critical: you only have the SPOKEN transcript, not the video, so
you do not actually know the name of the game, show, or brand
being played/discussed unless it is explicitly said out loud in
the transcript below. NEVER invent, guess, or assume a specific
game title, franchise, or brand name. If no name is spoken,
write the title generically (e.g. "Gila, Serangan Balik Dadakan!"
instead of inventing "Riftstorm Comeback!") — describe the
moment itself, not a made-up product name.

Return ONLY JSON in this format:

[
  {{
    "start": 120.0,
    "end": 153.0,
    "title": "Short title",
    "reason": "Why this hook is interesting",
    "score": 92,
    "content_type": "Funny",
    "rating": 8
  }}
]

Transcript:

{timed_transcript}
"""

    raw, ai_meta = ai_router.ai_generate_json(
        prompt,
        HOOKS_SCHEMA,
        task="hooks",
        # Claude's adaptive thinking counts against this.
        max_tokens=16000,
        with_meta=True,
    )

    log(
        f"Hooks produced by {ai_meta['provider']} "
        f"({ai_meta['model']})"
        + (" after failover" if ai_meta["failed_over"] else "")
    )

    if not isinstance(
        raw,
        list,
    ):

        raise RuntimeError(
            f"{ai_meta['provider']} did not return a list"
        )

    results = []

    for item in raw:

        if not isinstance(
            item,
            dict,
        ):
            continue

        try:

            start = float(
                item["start"]
            )

            end = float(
                item["end"]
            )

        except Exception:

            continue

        duration = (
            end - start
        )

        if duration < 5:

            continue

        if duration > 60:

            end = start + 60

        allowed_content_types = {
            "Funny",
            "Wise",
            "Reality",
            "Hype",
            "Wholesome",
            "Educational",
        }

        content_type = str(
            item.get(
                "content_type",
                "",
            )
        ).strip()

        if content_type not in allowed_content_types:

            content_type = "Reality"

        try:

            rating = int(
                item.get(
                    "rating",
                    5,
                )
            )

        except Exception:

            rating = 5

        rating = max(
            1,
            min(
                10,
                rating,
            ),
        )

        results.append(
            {
                "start": start,

                "end": end,

                "title":
                    str(
                        item.get(
                            "title",
                            "AI Short Clip",
                        )
                    )[:120],

                "reason":
                    str(
                        item.get(
                            "reason",
                            "",
                        )
                    )[:1000],

                "score":
                    int(
                        item.get(
                            "score",
                            0,
                        )
                    ),

                "content_type": content_type,

                "rating": rating,

                "provider": ai_meta["provider"],
            }
        )

    if len(results) < 1:

        raise RuntimeError(
            f"{ai_meta['provider']} returned no usable clips"
        )

    results.sort(
        key=lambda x:
            x["score"],
        reverse=True,
    )

    return results[
        :clip_count
    ]


# ============================================================
# SEGMENT UTILITIES
# ============================================================

def extract_clip_segments(
    segments,
    start,
    end,
):

    result = []

    for segment in segments:

        if segment["end"] <= start:

            continue

        if segment["start"] >= end:

            continue

        seg_start = max(
            0,
            segment["start"] - start,
        )

        seg_end = min(
            end - start,
            segment["end"] - start,
        )

        words = []

        for w in segment.get("words", []) or []:

            w_start = w["start"] - start
            w_end = w["end"] - start

            if w_end <= 0 or w_start >= (end - start):
                continue

            words.append({
                "word": w["word"],
                "start": max(0, w_start),
                "end": min(end - start, w_end),
            })

        result.append(
            {
                "start": seg_start,

                "end": seg_end,

                "text":
                    segment["text"],

                "words": words,
            }
        )

    return result


def apply_subtitle_override(
    original_segments,
    override_text,
    clip_duration,
):

    if not override_text:

        return original_segments

    lines = [
        line.strip()
        for line in override_text.splitlines()
        if line.strip()
    ]

    if not lines:

        return original_segments

    if len(lines) == len(
        original_segments
    ):

        result = []

        for segment, text in zip(
            original_segments,
            lines,
        ):

            item = dict(
                segment
            )

            item["text"] = text

            # The user hand-edited this line's wording, so the
            # original per-word timings no longer line up with
            # what's actually written — drop them and fall back to
            # a plain static line rather than highlighting the
            # wrong words.
            item["words"] = []

            result.append(
                item
            )

        return result

    slice_duration = (
        clip_duration
        / len(lines)
    )

    result = []

    for index, text in enumerate(
        lines
    ):

        result.append(
            {
                "start":
                    index * slice_duration,

                "end":
                    min(
                        clip_duration,
                        (index + 1)
                        * slice_duration,
                    ),

                "text":
                    text,

                "words": [],
            }
        )

    return result


# ============================================================
# SUBTITLE STYLE NORMALIZATION
# ============================================================

def normalize_subtitle_style(
    style
):

    # Database JSONB may return a dict.
    if isinstance(
        style,
        dict,
    ):

        # If UI stored a named style:
        name = style.get(
            "style"
        )

        if isinstance(
            name,
            str,
        ):

            return name

        name = style.get(
            "name"
        )

        if isinstance(
            name,
            str,
        ):

            return name

        # Otherwise select a safe style.
        if style.get(
            "bold"
        ):

            return "bold"

        return "clean"

    if isinstance(
        style,
        str,
    ):

        if style in {
            "bold",
            "clean",
            "outline",
            "boxed",
        }:

            return style

    return "bold"


def normalize_subtitle_font(
    job
):

    style = job.get(
        "subtitle_style"
    )

    if isinstance(
        style,
        dict,
    ):

        font = style.get(
            "font"
        )

        if font:

            return str(
                font
            )

    return (
        job.get(
            "subtitle_font"
        )
        or "Liberation Sans Bold"
    )


def normalize_subtitle_size(
    job,
    default=42,
):

    style = job.get(
        "subtitle_style"
    )

    if isinstance(
        style,
        dict,
    ):

        size = style.get(
            "size"
        )

        if size is not None:

            try:

                return int(
                    size
                )

            except Exception:

                pass

    try:

        return int(
            job.get(
                "subtitle_size",
                default,
            )
            or default
        )

    except Exception:

        return default


def normalize_subtitle_animation(
    job,
    default="karaoke",
):
    """
    Mirrors normalize_subtitle_font/size: the subtitle_style JSONB
    (when present) wins, falling back to the job's dedicated
    subtitle_animation column, falling back to the default.
    """

    style = job.get(
        "subtitle_style"
    )

    if isinstance(
        style,
        dict,
    ):

        animation = style.get(
            "animation"
        )

        if isinstance(
            animation,
            str,
        ) and animation.strip():

            return animation.strip().lower()

    value = job.get(
        "subtitle_animation"
    )

    if isinstance(
        value,
        str,
    ) and value.strip():

        return value.strip().lower()

    return default


# ============================================================
# VIDEO METADATA
# ============================================================

def metadata(
    video_path
):

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open video with OpenCV: "
            + str(video_path)
        )

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    fps = float(
        capture.get(
            cv2.CAP_PROP_FPS
        )
    )

    frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    duration = (
        frames / fps
        if fps > 0
        else 0
    )

    capture.release()

    if width <= 0 or height <= 0:

        raise RuntimeError(
            "Invalid video dimensions: "
            f"{width}x{height}"
        )

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frames": frames,
        "duration": duration,
    }


# ============================================================
# FACE DETECTION
# ============================================================

_face_net = None


def face_net():

    global _face_net

    if _face_net is None:

        if not FACE_PROTO_PATH.exists():

            raise RuntimeError(
                "Missing face detector prototxt: "
                + str(FACE_PROTO_PATH)
            )

        if not FACE_MODEL_PATH.exists():

            raise RuntimeError(
                "Missing face detector model: "
                + str(FACE_MODEL_PATH)
            )

        _face_net = (
            cv2.dnn.readNetFromCaffe(
                str(
                    FACE_PROTO_PATH
                ),
                str(
                    FACE_MODEL_PATH
                ),
            )
        )

    return _face_net


def detect_faces(
    image
):

    network = face_net()

    min_confidence = setting_float(
        "FACE_CONFIDENCE_THRESHOLD"
    )

    height, width = (
        image.shape[:2]
    )

    if height == 0 or width == 0:
        return []

    blob = (
        cv2.dnn.blobFromImage(
            image,
            1.0,
            (300, 300),
            (
                104.0,
                177.0,
                123.0,
            ),
        )
    )

    network.setInput(
        blob
    )

    detections = (
        network.forward()
    )

    result = []

    for index in range(
        detections.shape[2]
    ):

        confidence = float(
            detections[
                0,
                0,
                index,
                2,
            ]
        )

        if confidence < min_confidence:

            continue

        box = (
            detections[
                0,
                0,
                index,
                3:7,
            ]
            * [
                width,
                height,
                width,
                height,
            ]
        )

        x1, y1, x2, y2 = (
            box.astype(int)
        )

        x1 = max(
            0,
            x1,
        )

        y1 = max(
            0,
            y1,
        )

        x2 = min(
            width,
            x2,
        )

        y2 = min(
            height,
            y2,
        )

        if (
            x2 <= x1
            or y2 <= y1
        ):

            continue

        result.append(
            {
                "x": int(x1),
                "y": int(y1),
                "w": int(x2 - x1),
                "h": int(y2 - y1),
                "confidence":
                    float(confidence),
            }
        )

    return result


def detect_faces_in_corners(
    frame,
    corner_fraction=0.42,
):
    """
    Run the face detector on each corner of the frame cropped at
    NATIVE resolution, in addition to whatever the caller already
    ran on the full downscaled frame. A small embedded webcam PiP
    shrinks to almost nothing once the whole frame is downscaled
    to the detector's 300x300 input, so this searches the corners
    directly at full resolution and maps results back to absolute
    frame coordinates.
    """

    height, width = frame.shape[:2]

    corner_w = int(width * corner_fraction)
    corner_h = int(height * corner_fraction)

    regions = {
        "bottom_right": (
            width - corner_w,
            height - corner_h,
            corner_w,
            corner_h,
        ),
        "bottom_left": (
            0,
            height - corner_h,
            corner_w,
            corner_h,
        ),
        "top_right": (
            width - corner_w,
            0,
            corner_w,
            corner_h,
        ),
        "top_left": (
            0,
            0,
            corner_w,
            corner_h,
        ),
    }

    found = []

    for region_name, (rx, ry, rw, rh) in regions.items():

        region_frame = frame[ry:ry + rh, rx:rx + rw]

        if region_frame.size == 0:
            continue

        try:
            faces = detect_faces(region_frame)
        except Exception as exc:
            log(
                "Corner face detection failed ("
                + region_name
                + "): "
                + str(exc)
            )
            continue

        for face in faces:

            found.append(
                {
                    "x": face["x"] + rx,
                    "y": face["y"] + ry,
                    "w": face["w"],
                    "h": face["h"],
                    "confidence": face["confidence"],
                }
            )

    return found


def detect_face_for_clip(
    video_path,
    start,
    end,
    layout="auto",
):
    """
    layout: "auto" (default) scores every corner evenly, exactly as
    before. "left"/"right" is a user-provided hint (set on the job
    before analysis even starts) that the facecam sits on that side —
    detections on that side are strongly preferred, and if nothing is
    detected at all, the fallback box sits on that side too, instead
    of always defaulting to bottom-right.
    """

    layout = (layout or "auto").strip().lower()
    if layout not in ("auto", "left", "right"):
        layout = "auto"

    info = metadata(
        video_path
    )

    width = info["width"]
    height = info["height"]

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        raise RuntimeError(
            "OpenCV cannot open normalized video"
        )

    samples = max(
        6,
        setting_int("FACE_DETECTION_SAMPLE_COUNT"),
    )

    clip_duration = max(
        1,
        end - start,
    )

    detections = []

    for index in range(
        samples
    ):

        timestamp = (
            start
            + (
                clip_duration
                * index
                / max(
                    1,
                    samples - 1,
                )
            )
        )

        capture.set(
            cv2.CAP_PROP_POS_MSEC,
            timestamp * 1000,
        )

        ok, frame = (
            capture.read()
        )

        if not ok:

            continue

        try:

            full_frame_faces = detect_faces(
                frame
            )

        except Exception as exc:

            log(
                "Face detection sample failed: "
                + str(exc)
            )

            full_frame_faces = []

        try:

            corner_faces = detect_faces_in_corners(
                frame
            )

        except Exception as exc:

            log(
                "Corner face detection sample failed: "
                + str(exc)
            )

            corner_faces = []

        for face in full_frame_faces + corner_faces:

            cx = (
                face["x"]
                + face["w"] / 2
            )

            cy = (
                face["y"]
                + face["h"] / 2
            )

            area_ratio = (
                face["w"]
                * face["h"]
                / (
                    width
                    * height
                )
            )

            corner_x = min(
                cx,
                width - cx,
            )

            corner_y = min(
                cy,
                height - cy,
            )

            corner_score = (
                1
                - (
                    corner_x / width
                    + corner_y / height
                )
                / 2
            )

            # When the user told us which side the facecam is on,
            # strongly reward detections on that side and penalize
            # the opposite side — this is what actually makes "left"/
            # "right" stick instead of the auto corner-scoring
            # overriding it.
            if layout == "left":
                side_score = 1.0 - (cx / width)
            elif layout == "right":
                side_score = cx / width
            else:
                side_score = None

            if side_score is None:
                score = (
                    face["confidence"]
                    * 0.45
                    + area_ratio
                    * 5
                    * 0.35
                    + corner_score
                    * 0.20
                )
            else:
                score = (
                    face["confidence"]
                    * 0.30
                    + area_ratio
                    * 5
                    * 0.20
                    + corner_score
                    * 0.10
                    + side_score
                    * 0.40
                )

            detections.append(
                {
                    "cx": float(cx),
                    "cy": float(cy),
                    "w": float(face["w"]),
                    "h": float(face["h"]),
                    "score": float(score),
                }
            )

    capture.release()

    if not detections:

        fallback_cx = {
            "left": width * 0.18,
            "right": width * 0.82,
            "auto": width * 0.82,
        }[layout]

        log(
            "No face detected; using "
            + ("left" if layout == "left" else "bottom-right")
            + " fallback"
        )

        return {
            "detected": False,
            "cx": fallback_cx,
            "cy": height * 0.78,
            "w": width * 0.15,
            "h": height * 0.22,
        }

    detections.sort(
        key=lambda x:
            x["score"],
        reverse=True,
    )

    best = detections[
        :min(
            10,
            len(detections),
        )
    ]

    return {
        "detected": True,

        "cx":
            statistics.median(
                [
                    x["cx"]
                    for x in best
                ]
            ),

        "cy":
            statistics.median(
                [
                    x["cy"]
                    for x in best
                ]
            ),

        "w":
            statistics.median(
                [
                    x["w"]
                    for x in best
                ]
            ),

        "h":
            statistics.median(
                [
                    x["h"]
                    for x in best
                ]
            ),
    }


# ============================================================
# FACE CROP
# ============================================================

FACE_CROP_CENTER_FLOOR = 0.60
FACE_CROP_MIN_HEIGHT_1080P = 120


def calculate_face_crop(
    source_width,
    source_height,
    face,
    panel_width,
    panel_height,
):

    ratio = (
        panel_width
        / panel_height
    )

    # Face should fill roughly FACE_ZOOM_RATIO (default 78%) of the
    # crop's height for a tight, centered facecam look. Raising this fraction shrinks
    # the crop area around the face (more zoomed in).
    face_fill_ratio = setting_float("FACE_ZOOM_RATIO")

    desired_crop_height = (
        float(face["h"])
        / face_fill_ratio
    )

    # Minimum crop guards against a tiny (often false-positive)
    # detection zooming into a few pixels. It was a flat 180px, which
    # swallowed FACE_ZOOM_RATIO for typical corner-PIP webcams (a
    # ~110px face asks for 142-179px). R-04: 120px at 1080p, scaled
    # with the source height.
    min_crop_height = int(
        FACE_CROP_MIN_HEIGHT_1080P * source_height / 1080
    )

    crop_height = int(
        max(
            min_crop_height,
            desired_crop_height,
        )
    )

    # Safety clamp: even if detection produced an oversized or
    # false-positive box (e.g. a human-shaped character in the
    # game itself), never let the crop exceed a sane fraction of
    # the source frame. Without this, a bad detection can zoom
    # OUT instead of in.
    max_crop_height = int(
        source_height * 0.55
    )

    crop_height = min(
        crop_height,
        max_crop_height,
    )

    crop_width = int(
        crop_height
        * ratio
    )

    if crop_width > source_width:

        crop_width = source_width

        crop_height = int(
            crop_width
            / ratio
        )

    if crop_height > source_height:

        crop_height = source_height

        crop_width = int(
            crop_height
            * ratio
        )

    # Guarantee the crop CAN be perfectly centered on the face, even
    # when the source facecam sits near a corner/edge of the frame
    # (very common: the streamer's own webcam overlay is usually a
    # small PIP box tucked in a corner of the source recording).
    # Without this, edge-clamping below would silently shift the
    # face off-center toward whichever edge it's closest to — which
    # then lines up with the native right-hand action rail on
    # YouTube Shorts / TikTok / Instagram Reels. Shrinking the crop
    # (a slightly tighter zoom) is a small trade for a face that is
    # always dead-center in the facecam pane.
    max_half_width = max(
        1,
        min(
            face["cx"],
            source_width - face["cx"],
        ),
    )

    max_half_height = max(
        1,
        min(
            face["cy"],
            source_height - face["cy"],
        ),
    )

    requested_crop_height = crop_height

    centered_crop_height = min(
        crop_height,
        int(2 * max_half_width / ratio),
        int(2 * max_half_height),
    )

    # Floor (R-04): a face tight against a frame edge can collapse
    # the centered crop to a sliver (huge upscale, face cut off).
    # Below 60% of the requested height, keep 60% and accept that
    # the edge clamp further down frames the face slightly
    # off-center instead.
    # Also never smaller than the face itself, or the pane shows a
    # forehead-to-chin slice.
    crop_height_floor = min(
        requested_crop_height,
        max(
            int(requested_crop_height * FACE_CROP_CENTER_FLOOR),
            int(face["h"]),
        ),
    )

    if centered_crop_height < crop_height_floor:

        log(
            "Face crop: centering would shrink crop to "
            f"{centered_crop_height}px (floor {crop_height_floor}px of "
            f"requested {requested_crop_height}px); using the floor, "
            "face framed off-center"
        )

        crop_height = crop_height_floor

    else:

        crop_height = centered_crop_height

    crop_height = max(
        crop_height,
        1,
    )

    crop_width = int(
        crop_height
        * ratio
    )

    # Center the crop on the face both horizontally and
    # vertically (previous version biased 38% down from top,
    # which pushed the face off-center toward the bottom).
    crop_x = int(
        face["cx"]
        - crop_width / 2
    )

    crop_y = int(
        face["cy"]
        - crop_height / 2
    )

    crop_x = max(
        0,
        min(
            crop_x,
            source_width
            - crop_width,
        ),
    )

    crop_y = max(
        0,
        min(
            crop_y,
            source_height
            - crop_height,
        ),
    )

    return {
        "x": int(crop_x),
        "y": int(crop_y),
        "w": int(crop_width),
        "h": int(crop_height),
    }


# ============================================================
# SUBTITLE
# ============================================================

def ass_time(
    seconds
):

    seconds = max(
        0,
        float(seconds),
    )

    hours = int(
        seconds // 3600
    )

    minutes = int(
        seconds % 3600 // 60
    )

    sec = (
        seconds % 60
    )

    return (
        f"{hours}:"
        f"{minutes:02d}:"
        f"{sec:05.2f}"
    )



# Word-level entrance transforms used by ANIMATIONS below. Kept
# separate from color/weight presets so any color style can be
# combined with any animation. All are pure ASS override tags — no
# \move/\pos math, so they stay correct regardless of alignment/
# margins.
ANIMATION_ENTRANCE_TAGS = {

    # No per-word/per-line entrance effect at all — captions simply
    # appear, fully static. Used by the "none" animation.
    "none": "",

    # Today's original look: the whole line scales in from 82% to
    # 100% over 110ms.
    "pop_line": r"{\fscx82\fscy82\t(0,110,\fscx100\fscy100)}",

    # A single word scales up from ~55% while fading in — snappy,
    # MrBeast/Hormozi-style "big word pop".
    "pop_word": (
        r"{\fscx55\fscy55\alpha&HFF&"
        r"\t(0,120,\fscx100\fscy100\alpha&H00&)}"
    ),

    # Same idea but overshoots past 100% then settles — a cartoonish
    # bounce landing.
    "bounce_word": (
        r"{\fscx55\fscy55\alpha&HFF&"
        r"\t(0,90,\fscx118\fscy118\alpha&H00&)"
        r"\t(90,170,\fscx100\fscy100)}"
    ),

    # Starts slightly oversized and fades in while shrinking back to
    # 100% — a soft "settle" rather than a hard pop.
    "fade_settle": (
        r"{\fscx112\fscy112\alpha&HFF&"
        r"\t(0,140,\fscx100\fscy100\alpha&H00&)}"
    ),

    # Quick, near-instant reveal — used for each newly-typed word in
    # the typewriter animation.
    "typewriter_word": r"{\fad(60,0)}",
}

# Selectable subtitle animation styles, independent of the color/
# font-weight "style" preset. "mode" controls how segments are laid
# out into ASS Dialogue events:
#   - "flow": one continuous line per segment with a \kf karaoke
#     fill-sweep (classic word-highlight-as-spoken).
#   - "chunk": short bursts of `chunk_size` words at a time, each its
#     own timed event using the "entrance" transform.
#   - "typewriter": words accumulate left-to-right within the line as
#     they're spoken.
# Keep the key set in sync with SUBTITLE_ANIMATIONS in main.py.
ANIMATIONS = {
    "karaoke": {
        "label": "Karaoke Sweep", "mode": "flow", "entrance": "pop_line",
    },
    "none": {
        "label": "Static (no animation)", "mode": "flow", "entrance": "none",
    },
    "word_pop": {
        "label": "Word Pop", "mode": "chunk", "chunk_size": 1,
        "entrance": "pop_word",
    },
    "bounce": {
        "label": "Bounce In", "mode": "chunk", "chunk_size": 1,
        "entrance": "bounce_word",
    },
    "fade_settle": {
        "label": "Fade & Settle", "mode": "chunk", "chunk_size": 2,
        "entrance": "fade_settle",
    },
    "typewriter": {
        "label": "Typewriter", "mode": "typewriter", "entrance": "none",
    },
}


def make_ass(
    segments,
    path,
    font,
    font_size,
    style,
    canvas_width,
    canvas_height,
    split_ratio=70,
    animation="karaoke",
    watermark_width=None,
):

    # IMPORTANT:
    # JSONB subtitle_style can arrive as a dict.
    # Convert it to a named style BEFORE styles.get().
    style = normalize_subtitle_style(
        style
    )

    animation = (animation or "karaoke").strip().lower()
    if animation not in ANIMATIONS:
        animation = "karaoke"

    anim = ANIMATIONS[animation]

    # Each preset controls purely the colors/weight/box look: whether
    # the box behind text is opaque (BorderStyle 3, a la Instagram-
    # native captions) or just an outline, the karaoke highlight/
    # resting colors, and an optional font-size multiplier. Motion —
    # karaoke sweep vs. word-by-word pop/bounce/typewriter — is fully
    # decoupled and controlled by `animation` above, so any color
    # style can be paired with any animation. Colors are (secondary/
    # resting, primary/highlighted-as-spoken) as #RRGGBB.
    styles = {

        "bold": {
            "label": "Bold Social",
            "bold": -1, "outline": 6, "shadow": 2, "border_style": 1,
            "resting": "#FFFFFF", "highlight": "#FFD60A", "back": "#000000",
            "size_mult": 1.0,
        },

        "outline": {
            "label": "Heavy Outline",
            "bold": -1, "outline": 9, "shadow": 1, "border_style": 1,
            "resting": "#FFFFFF", "highlight": "#FFD60A", "back": "#000000",
            "size_mult": 1.0,
        },

        "clean": {
            "label": "Clean",
            "bold": -1, "outline": 3, "shadow": 1, "border_style": 1,
            "resting": "#FFFFFF", "highlight": "#64D2FF", "back": "#000000",
            "size_mult": 0.92,
        },

        "boxed": {
            "label": "Bold Box",
            "bold": -1, "outline": 2, "shadow": 0, "border_style": 3,
            "resting": "#FFFFFF", "highlight": "#FFD60A", "back": "#000000",
            "size_mult": 1.0,
        },

        "hormozi": {
            "label": "Big Word Pop",
            "bold": -1, "outline": 10, "shadow": 0, "border_style": 1,
            "resting": "#FFD60A", "highlight": "#FFD60A", "back": "#000000",
            "size_mult": 1.4,
        },

        "neon": {
            "label": "Neon Pop",
            "bold": -1, "outline": 5, "shadow": 3, "border_style": 1,
            "resting": "#5CE1FF", "highlight": "#FF2D95", "back": "#000000",
            "size_mult": 1.0,
        },

        "minimal": {
            "label": "Minimal",
            "bold": -1, "outline": 2, "shadow": 0, "border_style": 1,
            "resting": "#FFFFFF", "highlight": "#E8E8ED", "back": "#000000",
            "size_mult": 0.85,
        },

        "impact": {
            "label": "Impact Red",
            "bold": -1, "outline": 4, "shadow": 1, "border_style": 1,
            "resting": "#FFFFFF", "highlight": "#FF3B30", "back": "#000000",
            "size_mult": 1.08,
        },

        "pastel": {
            "label": "Soft Pastel",
            "bold": -1, "outline": 2, "shadow": 1, "border_style": 1,
            "resting": "#FFF6EC", "highlight": "#FFB4C6", "back": "#000000",
            "size_mult": 0.95,
        },

        "gold": {
            "label": "Gold Classic",
            "bold": -1, "outline": 1, "shadow": 0, "border_style": 3,
            "resting": "#FFFFFF", "highlight": "#FFC300", "back": "#000000",
            "size_mult": 1.0,
        },
    }

    setting = styles.get(
        style,
        styles["bold"],
    )

    effective_size = max(
        12,
        int(round(font_size * setting.get("size_mult", 1.0))),
    )

    def to_ass_color(hex_color):
        hex_color = hex_color.lstrip("#")
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}"

    # MarginV is measured UPWARD from the bottom of the canvas.
    # Anchor it to the top of the facecam pane (the seam between
    # gameplay content and the creator's face) plus a small safety
    # gap, instead of a fixed offset. This keeps subtitles clear of
    # the facecam strip entirely (no more overlapping the creator's
    # face) while staying safely below the watermark, which sits
    # centered on the full canvas — the seam is always well under
    # the canvas's vertical center for any supported split ratio.
    bottom_pane_ratio = max(
        0,
        min(100, 100 - split_ratio),
    ) / 100

    seam_gap = canvas_height * 0.04

    margin_v = int(
        canvas_height * bottom_pane_ratio
        + seam_gap
    )

    # The watermark just got bigger and fully opaque, which shrinks
    # the safe gap above the facecam seam — enough that the 60:40
    # split combined with a large preset (Big Word Pop) could push
    # captions up into the watermark's own footprint. Read the
    # watermark's real pixel size and pull margin_v down if needed
    # so captions always clear its bottom edge, with a bit of buffer.
    wm_size = _watermark_pixel_size()

    if wm_size:

        wm_natural_w, wm_natural_h = wm_size

        wm_render_w = (
            (watermark_width or setting_int("WATERMARK_WIDTH"))
            * canvas_width / FINAL_WIDTH
        )

        wm_render_h = (
            wm_natural_h * wm_render_w / wm_natural_w
        )

        wm_bottom = (
            canvas_height + wm_render_h
        ) / 2

        buffer = canvas_height * 0.035

        safe_margin_v = int(
            canvas_height - wm_bottom - buffer
        )

        margin_v = min(
            margin_v,
            max(0, safe_margin_v),
        )

    # PrimaryColour is the "already spoken" fill color words sweep
    # into (karaoke highlight); SecondaryColour is the resting/
    # not-yet-spoken color — both are per-preset now, so "Clean"
    # stays cool/subtle while "Hormozi"/"Neon" pop hard. ASS colors
    # are &HAABBGGRR (blue/green/red swapped, alpha 00 = opaque).
    lines = [
        "[Script Info]",

        "ScriptType: v4.00+",

        f"PlayResX: {canvas_width}",

        f"PlayResY: {canvas_height}",

        "",

        "[V4+ Styles]",

        (
            "Format: Name,Fontname,"
            "Fontsize,PrimaryColour,"
            "SecondaryColour,"
            "OutlineColour,"
            "BackColour,Bold,"
            "Italic,Underline,"
            "StrikeOut,ScaleX,"
            "ScaleY,Spacing,Angle,"
            "BorderStyle,Outline,"
            "Shadow,Alignment,"
            "MarginL,MarginR,"
            "MarginV,Encoding"
        ),

        (
            f"Style: Default,"
            f"{font},"
            f"{effective_size},"
            f"{to_ass_color(setting['highlight'])},"
            f"{to_ass_color(setting['resting'])},"
            "&H00000000,"
            f"{to_ass_color(setting['back'])},"
            f"{setting['bold']},"
            "0,0,0,"
            "100,100,0,0,"
            f"{setting['border_style']},"
            f"{setting['outline']},"
            f"{setting['shadow']},"
            f"2,40,40,{margin_v},1"
        ),

        "",

        "[Events]",

        (
            "Format: Layer,Start,End,"
            "Style,Name,MarginL,"
            "MarginR,MarginV,"
            "Effect,Text"
        ),
    ]

    def esc(raw_text):
        return (
            raw_text
            .replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
        )

    mode = anim["mode"]
    chunk_size = anim.get("chunk_size", 1)
    entrance_tag = ANIMATION_ENTRANCE_TAGS.get(anim["entrance"], "")

    # Only the "karaoke" animation gets the classic word-by-word
    # \kf color sweep — "none" (and anything falling back to flow
    # rendering) is a genuinely static line, not just missing an
    # entrance pop.
    karaoke_fill = mode == "flow" and animation == "karaoke"

    for segment in segments:

        raw_text = re.sub(
            r"\s+",
            " ",
            segment.get(
                "text",
                "",
            ).strip(),
        )

        if not raw_text:

            continue

        seg_start = float(segment.get("start", 0))
        seg_end = float(segment.get("end", seg_start))
        words = segment.get("words") or []

        has_word_timing = bool(words) and seg_end > seg_start

        # --------------------------------------------------
        # CHUNK animations (Word Pop / Bounce In / Fade &
        # Settle): short bursts of `chunk_size` words, each
        # its own timed event carrying the animation's
        # entrance transform. Falls through to flow/plain
        # rendering below if there's no word timing.
        # --------------------------------------------------
        if mode == "chunk" and has_word_timing:

            for i in range(0, len(words), chunk_size):

                group = words[i:i + chunk_size]
                g_start = float(group[0]["start"])
                g_end = float(group[-1]["end"])

                if g_end <= g_start:
                    continue

                chunk_text = esc(
                    " ".join(w["word"].strip() for w in group).upper()
                )

                if not chunk_text.strip():
                    continue

                lines.append(
                    "Dialogue: 0,"
                    f"{ass_time(g_start)},"
                    f"{ass_time(g_end)},"
                    "Default,,0,0,0,,"
                    + entrance_tag
                    + chunk_text
                )

            continue

        # --------------------------------------------------
        # TYPEWRITER: words accumulate left-to-right within
        # the line as they're spoken — each new word quickly
        # reveals the whole (growing) prefix. Falls through
        # to flow/plain rendering below if there's no word
        # timing.
        # --------------------------------------------------
        if mode == "typewriter" and has_word_timing:

            for i, w in enumerate(words):

                w_start = float(w["start"])

                if i + 1 < len(words):
                    w_end = float(words[i + 1]["start"])
                else:
                    w_end = seg_end

                if w_end <= w_start:
                    w_end = w_start + 0.05

                prefix_text = esc(
                    " ".join(
                        x["word"].strip() for x in words[:i + 1]
                    ).upper()
                )

                if not prefix_text.strip():
                    continue

                lines.append(
                    "Dialogue: 0,"
                    f"{ass_time(w_start)},"
                    f"{ass_time(w_end)},"
                    "Default,,0,0,0,,"
                    + ANIMATION_ENTRANCE_TAGS["typewriter_word"]
                    + prefix_text
                )

            continue

        # --------------------------------------------------
        # FLOW (default): one continuous line per segment.
        # With word timing AND the "karaoke" animation, each
        # word gets a \kf (smooth fill-sweep) block sized to
        # how long it's actually spoken, so the highlight
        # travels through the line in sync with the audio.
        # Gaps between words (or before the first word) get
        # their own silent \kf block so timing doesn't drift.
        # Any other case (no word timing, or the "none"
        # animation) renders as a plain static ALL CAPS line.
        # --------------------------------------------------
        built_from_words = None

        if has_word_timing and karaoke_fill:

            pieces = []
            cursor = seg_start

            for w in words:

                w_start = max(cursor, float(w["start"]))
                w_end = max(w_start, float(w["end"]))

                gap_cs = round((w_start - cursor) * 100)
                if gap_cs > 0:
                    pieces.append(f"{{\\kf{gap_cs}}} ")

                dur_cs = max(1, round((w_end - w_start) * 100))
                word_text = esc(w["word"].strip().upper())

                if word_text:
                    pieces.append(f"{{\\kf{dur_cs}}}{word_text}")

                cursor = w_end

            trailing_cs = round((seg_end - cursor) * 100)
            if trailing_cs > 0:
                pieces.append(f"{{\\kf{trailing_cs}}}")

            candidate_line = "".join(pieces).strip()

            if candidate_line:
                built_from_words = candidate_line

        if built_from_words:
            text = built_from_words
        else:
            # Fallback: no reliable word timing (manually edited
            # subtitle text, or Whisper couldn't align this
            # segment), or the "none" animation — render as a
            # plain static ALL CAPS line.
            text = esc(raw_text.upper())

        lines.append(
            "Dialogue: 0,"
            f"{ass_time(seg_start)},"
            f"{ass_time(seg_end)},"
            "Default,,0,0,0,,"
            + entrance_tag
            + text
        )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# VIDEO RENDER
# ============================================================

def job_watermark(job):
    """(width_px_at_1080, opacity) for a job: jobs.watermark_width /
    watermark_opacity when set (R-05), else the global settings.
    Read once per render so the ASS margin and the overlay agree."""
    width = job.get("watermark_width")
    opacity = job.get("watermark_opacity")
    if not width:
        width = setting_int("WATERMARK_WIDTH")
    if opacity is None:
        opacity = setting_float("WATERMARK_OPACITY")
    return (
        max(50, min(FINAL_WIDTH, int(width))),
        max(0.0, min(1.0, float(opacity))),
    )


def apply_watermark_overlay(
    source_path,
    output_path,
    *,
    watermark_width,
    watermark_opacity,
):
    """One overlay pass on an already-rendered vertical video (used
    after the Submagic download, R-05): same centered geometry as
    render_vertical(), audio copied."""

    watermark = resolve_watermark_path()

    if not watermark.exists():
        raise RuntimeError(
            "Required watermark missing: " + str(watermark)
        )

    cap = cv2.VideoCapture(str(source_path))
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or FINAL_WIDTH)
    cap.release()

    wm_width = max(2, int(watermark_width * video_width / FINAL_WIDTH))

    run_command(
        [
            "ffmpeg",
            "-y",
            "-hwaccel",
            "none",
            "-i",
            str(source_path),
            "-loop",
            "1",
            "-i",
            str(watermark),
            "-filter_complex",
            (
                f"[1:v]scale={wm_width}:-1,format=rgba,"
                f"colorchannelmixer=aa={watermark_opacity}[wm];"
                "[0:v][wm]overlay=(W-w)/2:(H-h)/2:shortest=1[video]"
            ),
            "-map",
            "[video]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            setting("FFMPEG_PRESET"),
            "-crf",
            setting("FFMPEG_CRF"),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def render_vertical(
    source_path,
    output_path,
    *,
    start,
    duration,
    face_crop,
    split_ratio,
    subtitle_path=None,
    preview=False,
    size=None,
    watermark_width=None,
    watermark_opacity=None,
    watermark=True,
):
    """Stack content (top) + facecam (bottom), then optionally the
    watermark and burned-in subtitles. subtitle_path=None skips the
    subtitles (R-06 clean plate, R-09 burn-in off); watermark=False
    skips the overlay and its input (R-06 clean plate)."""

    if preview:

        # create_preview passes the size it computed the crop and
        # ASS for, so a settings change mid-render can't split them.
        width, height = size or preview_size()

        preset = setting("FFMPEG_PREVIEW_PRESET")

        crf = setting("FFMPEG_PREVIEW_CRF")

    else:

        width = FINAL_WIDTH
        height = FINAL_HEIGHT

        preset = setting("FFMPEG_PRESET")

        crf = setting("FFMPEG_CRF")

    top_height = int(
        height
        * split_ratio
        / 100
    )

    bottom_height = (
        height
        - top_height
    )

    filters = []

    # --------------------------------------------------------
    # CONTENT TOP 70%
    # --------------------------------------------------------

    filters.append(
        (
            "[0:v]"
            f"scale={width}:"
            f"{top_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:"
            f"{top_height},"
            "setsar=1"
            "[content];"
        )
    )

    # --------------------------------------------------------
    # FACECAM BOTTOM 30%
    # --------------------------------------------------------

    filters.append(
        (
            "[0:v]"
            f"crop="
            f"{face_crop['w']}:"
            f"{face_crop['h']}:"
            f"{face_crop['x']}:"
            f"{face_crop['y']},"
            f"scale={width}:"
            f"{bottom_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:"
            f"{bottom_height},"
            "setsar=1"
            "[face];"
        )
    )

    # --------------------------------------------------------
    # STACK
    # --------------------------------------------------------

    filters.append(
        (
            "[content][face]"
            "vstack=inputs=2,"
            "format=yuv420p"
            "[stacked];"
        )
    )

    last = "stacked"

    # --------------------------------------------------------
    # WATERMARK (optional)
    # --------------------------------------------------------

    watermark_path = None

    if watermark:

        watermark_path = (
            resolve_watermark_path()
        )

        if not watermark_path.exists():

            raise RuntimeError(
                "Required watermark missing: "
                + str(watermark_path)
            )

        # Per-job values (R-05) come from job_watermark(); None falls
        # back to the global settings.
        if watermark_width is None or watermark_opacity is None:
            default_width, default_opacity = job_watermark({})
            watermark_width = watermark_width or default_width
            if watermark_opacity is None:
                watermark_opacity = default_opacity

        wm_width = int(
            watermark_width
            * width
            / FINAL_WIDTH
        )

        filters.append(
            (
                "[1:v]"
                f"scale={wm_width}:-1,"
                "format=rgba,"
                "colorchannelmixer="
                f"aa={watermark_opacity}"
                "[wm];"
            )
        )

        filters.append(
            (
                f"[{last}][wm]"
                "overlay="
                "(W-w)/2:"
                "(H-h)/2:"
                "shortest=1"
                "[watermarked];"
            )
        )

        last = "watermarked"

    # --------------------------------------------------------
    # SUBTITLE (optional)
    # --------------------------------------------------------

    if subtitle_path:

        escaped_subtitle = str(
            subtitle_path
        ).replace(
            "'",
            r"\'",
        )

        filters.append(
            (
                f"[{last}]"
                "subtitles="
                f"'{escaped_subtitle}'"
                "[subtitled];"
            )
        )

        last = "subtitled"

    # Every optional stage above ends in ";" and names its output;
    # the graph's final label must be [video] whichever stages ran.
    filters.append(
        f"[{last}]null[video]"
    )

    # --------------------------------------------------------
    # FFMPEG
    # --------------------------------------------------------

    command = [
        "ffmpeg",
        "-y",

        # Explicit software decoding.
        "-hwaccel",
        "none",

        "-ss",
        str(
            max(
                0,
                start,
            )
        ),

        "-i",
        str(source_path),

        *(
            ["-loop", "1", "-i", str(watermark_path)]
            if watermark_path else []
        ),

        "-t",
        str(
            max(
                1,
                duration,
            )
        ),

        "-filter_complex",
        "".join(filters),

        "-map",
        "[video]",

        "-map",
        "0:a?",

        "-c:v",
        "libx264",

        "-preset",
        preset,

        "-crf",
        str(crf),

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        (
            "96k"
            if preview
            else "128k"
        ),

        "-movflags",
        "+faststart",

        str(output_path),
    ]

    run_command(
        command
    )


# ============================================================
# CREATE PREVIEW
# ============================================================

def clean_plate_path(candidate_id):
    return PREVIEW_DIR / (str(candidate_id) + "_clean.mp4")


def render_clean_plate(
    candidate,
    job,
    video_path,
):
    """Full-size stacked render with NO subtitles and NO watermark
    (R-06): what Submagic gets, so its captions are the only ones and
    our watermark goes on after its render (R-05). Cached as
    <candidate_id>_clean.mp4; create_preview() deletes it, so any
    edit that re-renders the preview (new hook, trims) invalidates it."""

    output_path = clean_plate_path(candidate["id"])

    if output_path.exists() and output_path.stat().st_size > 0:
        log(f"Clean plate cached: {output_path.name}")
        return output_path

    start = float(candidate["start_time"])
    end = float(candidate["end_time"])

    face = detect_face_for_clip(
        video_path,
        start,
        end,
        layout=job.get("layout", "auto"),
    )

    info = metadata(video_path)

    split_ratio = int(job.get("split_ratio", 70) or 70)

    face_crop = calculate_face_crop(
        info["width"],
        info["height"],
        face,
        FINAL_WIDTH,
        FINAL_HEIGHT - int(FINAL_HEIGHT * split_ratio / 100),
    )

    # Render to a temp name so a crash never leaves a truncated file
    # that the cache check above would trust.
    tmp_path = output_path.with_suffix(".tmp.mp4")

    render_vertical(
        video_path,
        tmp_path,
        start=start,
        duration=end - start,
        face_crop=face_crop,
        split_ratio=split_ratio,
        subtitle_path=None,
        preview=False,
        watermark=False,
    )

    tmp_path.replace(output_path)

    return output_path


def create_preview(
    candidate,
    job,
    video_path,
):

    candidate_id = (
        candidate["id"]
    )

    # Any preview re-render means the clip may have changed (new
    # hook, new times): drop the cached Submagic clean plate (R-06).
    clean_plate_path(candidate_id).unlink(missing_ok=True)

    start = float(
        candidate["start_time"]
    )

    end = float(
        candidate["end_time"]
    )

    duration = (
        end - start
    )

    all_segments = (
        job.get(
            "transcript_segments"
        )
        or []
    )

    clip_segments = (
        extract_clip_segments(
            all_segments,
            start,
            end,
        )
    )

    clip_segments = (
        apply_subtitle_override(
            clip_segments,
            candidate.get(
                "subtitle_override"
            ),
            duration,
        )
    )

    # --------------------------------------------------------
    # FACE DETECTION
    # --------------------------------------------------------

    face = (
        detect_face_for_clip(
            video_path,
            start,
            end,
            layout=job.get("layout", "auto"),
        )
    )

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    info = metadata(
        video_path
    )

    split_ratio = int(
        job.get(
            "split_ratio",
            70,
        )
        or 70
    )

    # Read once: the ASS caption margin and the overlay must agree.
    wm_width, wm_opacity = job_watermark(job)

    preview_width, preview_height = preview_size()

    preview_bottom = (
        preview_height
        - int(
            preview_height
            * split_ratio
            / 100
        )
    )

    face_crop = (
        calculate_face_crop(
            info["width"],
            info["height"],
            face,
            preview_width,
            preview_bottom,
        )
    )

    # --------------------------------------------------------
    # SUBTITLE
    # --------------------------------------------------------

    subtitle_file = (
        SUBTITLE_DIR
        / (
            str(candidate_id)
            + "_preview.ass"
        )
    )

    preview_font_size = max(
        18,
        int(
            normalize_subtitle_size(
                job
            )
            * preview_width
            / FINAL_WIDTH
        ),
    )

    subtitle_style = (
        job.get(
            "subtitle_style"
        )
        or "outline"
    )

    subtitle_font = (
        normalize_subtitle_font(
            job
        )
    )

    make_ass(
        clip_segments,
        subtitle_file,
        subtitle_font,
        preview_font_size,
        subtitle_style,
        preview_width,
        preview_height,
        split_ratio=split_ratio,
        animation=normalize_subtitle_animation(job),
        watermark_width=wm_width,
    )

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    preview_path = (
        PREVIEW_DIR
        / (
            str(candidate_id)
            + ".mp4"
        )
    )

    render_vertical(
        video_path,
        preview_path,
        start=start,
        duration=duration,
        face_crop=face_crop,
        split_ratio=split_ratio,
        subtitle_path=subtitle_file,
        preview=True,
        size=(preview_width, preview_height),
        watermark_width=wm_width,
        watermark_opacity=wm_opacity,
    )

    # A locked thumbnail (an AI option or a manual upload the user
    # explicitly picked via Apply changes) must survive preview
    # regeneration — only grab a fresh frame when nothing's been
    # chosen yet.
    thumbnail_locked = bool(
        candidate.get("thumbnail_locked")
    )

    if thumbnail_locked:

        thumbnail_path = candidate.get("thumbnail_path")

    else:

        thumbnail_path = (
            PREVIEW_DIR
            / (str(candidate_id) + ".jpg")
        )
        create_thumbnail(
            preview_path,
            thumbnail_path,
        )

    subtitle_text = "\n".join(
        item["text"]
        for item in clip_segments
    )

    update_fields = dict(

        preview_path=
            str(preview_path),

        face_crop=
            json.dumps(
                face_crop
            ),

        subtitle_segments=
            json.dumps(
                clip_segments
            ),

        subtitle_override=(
            candidate.get(
                "subtitle_override"
            )
            or subtitle_text
        ),

    )

    if not thumbnail_locked:
        update_fields["thumbnail_path"] = str(thumbnail_path)

    update_candidate(
        candidate_id,
        **update_fields,
        status=
            "review",

        progress=100,

        message=
            "Preview ready",
    )


# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(video_path, thumbnail_path):
    """
    Extract a compact JPEG thumbnail from the rendered preview/final clip.
    """
    thumbnail_path = Path(thumbnail_path)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    run_command(
        [
            "ffmpeg",
            "-y",
            "-hwaccel",
            "none",
            "-ss",
            "0.5",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=360:-2",
            "-q:v",
            "3",
            str(thumbnail_path),
        ]
    )

    if not thumbnail_path.exists():
        raise RuntimeError(
            "Thumbnail was not created: " + str(thumbnail_path)
        )

    return thumbnail_path


# ============================================================
# FINAL RENDER
# ============================================================

def render_final_candidate(
    candidate,
    job,
    video_path,
):

    candidate_id = (
        candidate["id"]
    )

    start = float(
        candidate["start_time"]
    )

    end = float(
        candidate["end_time"]
    )

    duration = (
        end - start
    )

    all_segments = (
        job.get(
            "transcript_segments"
        )
        or []
    )

    clip_segments = (
        extract_clip_segments(
            all_segments,
            start,
            end,
        )
    )

    clip_segments = (
        apply_subtitle_override(
            clip_segments,
            candidate.get(
                "subtitle_override"
            ),
            duration,
        )
    )

    face = (
        detect_face_for_clip(
            video_path,
            start,
            end,
            layout=job.get("layout", "auto"),
        )
    )

    info = metadata(
        video_path
    )

    split_ratio = int(
        job.get(
            "split_ratio",
            70,
        )
        or 70
    )

    # Read once: the ASS caption margin and the overlay must agree.
    wm_width, wm_opacity = job_watermark(job)

    final_bottom = (
        FINAL_HEIGHT
        - int(
            FINAL_HEIGHT
            * split_ratio
            / 100
        )
    )

    face_crop = (
        calculate_face_crop(
            info["width"],
            info["height"],
            face,
            FINAL_WIDTH,
            final_bottom,
        )
    )

    subtitle_file = (
        SUBTITLE_DIR
        / (
            str(candidate_id)
            + "_final.ass"
        )
    )

    make_ass(
        clip_segments,
        subtitle_file,

        normalize_subtitle_font(
            job
        ),

        normalize_subtitle_size(
            job
        ),

        job.get(
            "subtitle_style"
        )
        or "outline",

        FINAL_WIDTH,
        FINAL_HEIGHT,
        split_ratio=split_ratio,
        animation=normalize_subtitle_animation(job),
        watermark_width=wm_width,
    )

    output_path = (
        FINAL_DIR
        / (
            str(candidate_id)
            + ".mp4"
        )
    )

    render_vertical(
        video_path,
        output_path,
        start=start,
        duration=duration,
        face_crop=face_crop,
        split_ratio=split_ratio,
        subtitle_path=subtitle_file,
        preview=False,
        watermark_width=wm_width,
        watermark_opacity=wm_opacity,
    )

    # Same rule as the preview: don't clobber a thumbnail the user
    # explicitly locked in (AI pick or manual upload) with a fresh
    # frame grabbed from the final render.
    thumbnail_locked = bool(
        candidate.get("thumbnail_locked")
    )

    if thumbnail_locked:

        thumbnail_path = candidate.get("thumbnail_path")

    else:

        thumbnail_path = (
            FINAL_DIR
            / (str(candidate_id) + ".jpg")
        )
        create_thumbnail(
            output_path,
            thumbnail_path,
        )

    with db() as conn:

        conn.execute(
            """
            UPDATE clip_candidates
            SET final_path = %s,
                thumbnail_path = %s,
                face_crop = %s::jsonb,
                status = 'completed',
                progress = 100,
                message = 'Final render completed',
                rendered_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                str(output_path),
                str(thumbnail_path),
                json.dumps(face_crop),
                candidate_id,
            ),
        )

        conn.commit()


# ============================================================
# CLAIM INITIAL / REANALYSIS JOB
# ============================================================

def claim_analysis_job():

    with db() as conn:

        row = conn.execute(
            """
            SELECT
                j.*,
                sv.youtube_url,
                sv.source_path,
                sv.id AS source_id
            FROM jobs j
            JOIN source_videos sv
              ON sv.id = j.source_video_id
            WHERE j.status IN (
                'queued',
                'reanalyze_queued'
            )
            ORDER BY j.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ).fetchone()

        if not row:

            return None

        original_status = (
            row["status"]
        )

        conn.execute(
            """
            UPDATE jobs
            SET status = 'processing',
                started_at =
                    COALESCE(
                        started_at,
                        NOW()
                    ),
                message =
                    'Worker processing',
                error_stage = NULL,
                error_message = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                row["id"],
            ),
        )

        conn.commit()

    data = dict(
        row
    )

    data[
        "original_status"
    ] = original_status

    return data


# ============================================================
# ANALYSIS PIPELINE
# ============================================================

class StageTimer:
    """Logs how long each analysis stage took (R-07: measure before
    optimizing). start(name) closes the previous stage and returns
    the name, so `stage = timer.start("download")` keeps the existing
    error_stage bookkeeping."""

    def __init__(self, job_id):
        self.job_id = job_id
        self.started = time.monotonic()
        self.current = None
        self.current_started = None
        self.done = []

    def start(self, name):
        self._close()
        self.current = name
        self.current_started = time.monotonic()
        return name

    def _close(self):
        if self.current is None:
            return
        elapsed = time.monotonic() - self.current_started
        self.done.append((self.current, elapsed))
        log(f"Stage {self.current}: {elapsed:.1f}s")
        self.current = None

    def summary(self):
        self._close()
        total = time.monotonic() - self.started
        log(
            f"Stage timings job {self.job_id}: "
            + " | ".join(f"{n} {t:.1f}s" for n, t in self.done)
            + f" | total {total:.1f}s"
        )


def process_analysis_job(
    job
):

    job_id = job["id"]

    source_id = job["source_id"]

    # R-07: per-stage wall time, one summary line per job.
    timer = StageTimer(job_id)

    stage = timer.start("initialization")

    try:

        source_path = (
            Path(
                job["source_path"]
            )
            if job.get(
                "source_path"
            )
            else None
        )

        transcript = (
            job.get(
                "transcript"
            )
            or ""
        )

        segments = (
            job.get(
                "transcript_segments"
            )
            or []
        )

        # ----------------------------------------------------
        # INITIAL DOWNLOAD / TRANSCRIPTION
        # ----------------------------------------------------

        if job["original_status"] == "queued":

            stage = timer.start("download")

            update_job(
                job_id,
                progress=5,
                message="Downloading video",
            )

            source_path = (
                download_video(
                    job["youtube_url"],
                    job_id,
                )
            )

            # ------------------------------------------------
            # AV1 NORMALIZATION
            # ------------------------------------------------

            stage = timer.start("video_normalization")

            update_job(
                job_id,
                progress=10,
                message="Checking video codec",
            )

            source_path = (
                normalize_video(
                    source_path,
                    job_id,
                )
            )

            with db() as conn:

                conn.execute(
                    """
                    UPDATE source_videos
                    SET source_path = %s,
                        status = 'downloaded'
                    WHERE id = %s
                    """,
                    (
                        str(source_path),
                        source_id,
                    ),
                )

                conn.commit()

            stage = timer.start("audio_extraction")

            update_job(
                job_id,
                progress=15,
                message="Extracting audio",
            )

            audio = (
                extract_audio(
                    source_path,
                    job_id,
                )
            )

            stage = timer.start("transcription")

            update_job(
                job_id,
                progress=25,
                message="Transcribing audio",
            )

            transcript, segments = (
                transcribe(
                    audio
                )
            )

            with db() as conn:

                conn.execute(
                    """
                    UPDATE jobs
                    SET transcript = %s,
                        transcript_segments =
                            %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        transcript,
                        json.dumps(
                            segments
                        ),
                        job_id,
                    ),
                )

                conn.commit()

        else:

            # Reanalysis should use existing source path.
            if source_path:

                stage = timer.start("video_normalization")

                source_path = (
                    normalize_video(
                        source_path,
                        job_id,
                    )
                )

        # ----------------------------------------------------
        # VALIDATE SOURCE
        # ----------------------------------------------------

        if not source_path:

            raise RuntimeError(
                "Source video path missing"
            )

        if not source_path.exists():

            raise RuntimeError(
                "Source video file missing: "
                + str(source_path)
            )

        if not transcript:

            raise RuntimeError(
                "Transcript missing"
            )

        # ----------------------------------------------------
        # GEMINI
        # ----------------------------------------------------

        stage = timer.start("ai_analysis")

        update_job(
            job_id,
            progress=45,
            message=(
                "AI analysing viral hooks"
            ),
        )

        # Read once: the prompt, the "enough clips" check and the
        # final review/partial decision must agree for this job.
        clip_count = setting_int("CLIP_COUNT")

        highlights = (
            analyze_hooks(
                transcript,
                segments,
                job.get("platform", "youtube_shorts"),
                clip_count=clip_count,
            )
        )

        if len(highlights) < clip_count:

            raise RuntimeError(
                f"AI returned only "
                f"{len(highlights)} usable clips; "
                f"{clip_count} required"
            )

        # ----------------------------------------------------
        # CLEAR OLD CANDIDATES
        # ----------------------------------------------------

        with db() as conn:

            conn.execute(
                """
                DELETE FROM clip_candidates
                WHERE job_id = %s
                """,
                (
                    job_id,
                ),
            )

            conn.commit()

        # ----------------------------------------------------
        # CREATE CANDIDATES
        # ----------------------------------------------------

        successful_candidates = 0
        failed_candidates = 0

        for index, highlight in enumerate(
            highlights
        ):

            candidate_id = (
                uuid.uuid4()
            )

            start = float(
                highlight["start"]
            )

            end = float(
                highlight["end"]
            )

            clip_segments = (
                extract_clip_segments(
                    segments,
                    start,
                    end,
                )
            )

            initial_subtitle = "\n".join(
                item["text"]
                for item in clip_segments
            )

            with db() as conn:

                row = conn.execute(
                    """
                    INSERT INTO clip_candidates (
                        id,
                        job_id,
                        clip_index,
                        start_time,
                        end_time,
                        reason,
                        ai_title,
                        subtitle_segments,
                        subtitle_override,
                        content_type,
                        rating,
                        hook_provider,
                        status,
                        progress,
                        message
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        %s,
                        %s,
                        %s,
                        %s,
                        'preview_rendering',
                        10,
                        'Creating preview'
                    )
                    RETURNING *
                    """,
                    (
                        candidate_id,
                        job_id,
                        index,
                        start,
                        end,
                        highlight.get(
                            "reason"
                        ),
                        highlight.get(
                            "title"
                        ),
                        json.dumps(
                            clip_segments
                        ),
                        initial_subtitle,
                        highlight.get("content_type", "Reality"),
                        int(highlight.get("rating", 5)),
                        highlight.get("provider"),
                    ),
                ).fetchone()

                conn.commit()

            stage = timer.start(
                f"preview_{index + 1}"
            )

            update_job(
                job_id,

                progress=(
                    60
                    + index * 15
                ),

                message=(
                    f"Rendering preview "
                    f"{index + 1}/"
                    f"{len(highlights)}"
                ),
            )

            try:

                create_preview(
                    row,
                    job,
                    source_path,
                )

                successful_candidates += 1

                log(
                    f"Candidate preview "
                    f"{index + 1} ready"
                )

            except Exception as exc:

                failed_candidates += 1

                detail = (
                    traceback.format_exc()
                )

                update_candidate(
                    candidate_id,

                    status="failed",

                    error_stage=
                        "preview_render",

                    error_message=(
                        str(exc)
                        + "\n\n"
                        + detail[-8000:]
                    ),

                    message=
                        "Preview failed",
                )

                log(
                    "Candidate preview "
                    f"{index + 1} failed: "
                    f"{exc}"
                )

        # ----------------------------------------------------
        # FINAL JOB STATE
        # ----------------------------------------------------

        if (
            successful_candidates
            == clip_count
        ):

            update_job(
                job_id,
                status="review",
                progress=100,
                message=(
                    "AI clips ready for review"
                ),
            )

            with db() as conn:

                conn.execute(
                    """
                    UPDATE jobs
                    SET review_ready_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        job_id,
                    ),
                )

                conn.commit()

            log(
                f"JOB READY FOR REVIEW: "
                f"{job_id}"
            )

        elif successful_candidates > 0:

            update_job(
                job_id,
                status="partial_failure",
                progress=100,
                message=(
                    f"{successful_candidates}/"
                    f"{clip_count} previews ready; "
                    f"{failed_candidates} failed"
                ),
                error_stage=
                    "preview_render",
                error=(
                    f"{failed_candidates} candidate(s) "
                    f"failed during preview rendering."
                ),
            )

            log(
                f"JOB PARTIAL FAILURE: "
                f"{job_id} "
                f"({successful_candidates}/"
                f"{clip_count})"
            )

        else:

            update_job(
                job_id,
                status="failed",
                progress=100,
                message=(
                    "All candidate previews failed"
                ),
                error_stage=
                    "preview_render",
                error=(
                    "All generated candidates "
                    "failed during preview rendering."
                ),
            )

            log(
                f"JOB FAILED: "
                f"{job_id} "
                f"(all previews failed)"
            )

    except Exception as exc:

        detail = (
            traceback.format_exc()
        )

        log(
            f"JOB FAILED "
            f"{job_id} "
            f"[{stage}]: "
            f"{exc}"
        )

        update_job(
            job_id,

            status="failed",

            message=
                "Processing failed",

            error_stage=
                stage,

            error=(
                str(exc)
                + "\n\n"
                + detail[-8000:]
            ),
        )

    finally:

        timer.summary()


# ============================================================
# AI THUMBNAILS (Runway)
# ============================================================
# Generates 3 candidate thumbnail images per clip. Each is a still frame
# pulled from the rendered clip (so framing/subtitles match reality),
# optionally re-imagined by Runway's image model (using the frame as a
# reference image) for a more scroll-stopping look. If Runway isn't
# configured or a call fails, that option quietly falls back to the
# plain extracted frame — the user always ends up with 3 choices.

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"


def extract_thumbnail_base_frame(
    video_path,
    t,
    face_crop,
    split_ratio,
    width,
    height,
    out_path,
):
    """Grab one still frame straight from the RAW source video and
    compose it into the same vertical gameplay-top / facecam-bottom
    layout the final render uses — but with no subtitles and no
    watermark baked in, since this is a clean plate meant to be
    AI-stylized and then have our own designed headline drawn on top.
    (Extracting from a preview/final render instead would capture
    whatever captions were already burned into that render.)
    """

    top_height = int(height * split_ratio / 100)
    bottom_height = height - top_height

    filter_complex = (
        "[0:v]"
        f"scale={width}:{top_height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{top_height},setsar=1[content];"
        "[0:v]"
        f"crop={face_crop['w']}:{face_crop['h']}:"
        f"{face_crop['x']}:{face_crop['y']},"
        f"scale={width}:{bottom_height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{bottom_height},setsar=1[face];"
        "[content][face]vstack=inputs=2,format=yuv420p[stacked]"
    )

    run_command(
        [
            "ffmpeg", "-y",
            "-ss", str(max(0.0, t)),
            "-i", str(video_path),
            "-frames:v", "1",
            "-filter_complex", filter_complex,
            "-map", "[stacked]",
            "-q:v", "2",
            str(out_path),
        ]
    )


_THUMBNAIL_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# Ties the thumbnail's accent band color to the clip's content_type,
# matching the same genre badges shown in the review UI, so the
# thumbnail and the in-app preview feel like one visual system.
_CONTENT_TYPE_ACCENT = {
    "Funny": (255, 149, 0),
    "Hype": (255, 59, 48),
    "Wholesome": (52, 199, 89),
    "Educational": (0, 113, 227),
    "Wise": (94, 92, 230),
    "Reality": (255, 214, 10),
}


def _thumbnail_font(size):
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    for path in _THUMBNAIL_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return None


def compose_thumbnail_headline(image_path, headline, content_type):
    """Draw a short, bold, high-contrast headline onto a thumbnail —
    the actual "designed thumbnail" layer, since AI image models
    render legible text unreliably. Placed in the upper third (the
    gameplay pane), clear of the facecam strip below, matching how
    real gaming thumbnails caption the action. Silently skipped if
    Pillow isn't installed, leaving the plain stylized frame."""

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log("Pillow not installed — skipping thumbnail headline text")
        return

    headline = re.sub(r"\s+", " ", (headline or "").strip()).upper()
    if not headline:
        return

    words = headline.split(" ")
    headline = " ".join(words[:7])[:60]

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return

    w, h = img.size
    accent = _CONTENT_TYPE_ACCENT.get(content_type, (255, 214, 10))

    font_size = max(36, int(w * 0.105))
    font = _thumbnail_font(font_size)
    if font is None:
        return

    draw = ImageDraw.Draw(img, "RGBA")

    # Wrap into at most 2 lines that fit within ~88% of the width,
    # shrinking the font a little if the headline is long.
    max_line_width = int(w * 0.88)

    def wrap(f):
        lines, current = [], ""
        for word in words[:7]:
            trial = (current + " " + word).strip()
            if draw.textlength(trial, font=f) <= max_line_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines[:2]

    lines = wrap(font)
    while len(lines) > 1 and font_size > 26 and any(
        draw.textlength(l, font=font) > max_line_width for l in lines
    ):
        font_size -= 4
        font = _thumbnail_font(font_size)
        if font is None:
            return
        lines = wrap(font)

    line_height = int(font_size * 1.18)
    block_height = line_height * len(lines) + int(font_size * 0.6)
    band_top = int(h * 0.10)
    band_bottom = min(int(h * 0.62), band_top + block_height + int(font_size * 0.5))

    # Soft dark band behind the text for legibility over any
    # background, plus a slim accent bar tying it to the genre color.
    draw.rectangle(
        [0, band_top, w, band_bottom],
        fill=(0, 0, 0, 110),
    )
    draw.rectangle(
        [0, band_top, int(w * 0.055), band_bottom],
        fill=(*accent, 255),
    )

    y = band_top + (band_bottom - band_top - block_height) // 2 + int(font_size * 0.3)

    for line in lines:
        line_w = draw.textlength(line, font=font)
        x = (w - line_w) / 2

        # Thick black outline (drawn as an 8-direction stroke) then
        # the accent-colored fill on top — bold, legible at feed
        # thumbnail size, same "punchy caption" language as the
        # burned-in subtitles.
        outline_px = max(2, font_size // 14)
        for dx in range(-outline_px, outline_px + 1, max(1, outline_px)):
            for dy in range(-outline_px, outline_px + 1, max(1, outline_px)):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))

        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    img.save(image_path, quality=92)


def runway_generate_image(
    frame_path,
    prompt,
    api_key,
    model,
    out_path,
):
    import base64

    try:
        b64 = base64.b64encode(
            Path(frame_path).read_bytes()
        ).decode("ascii")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": RUNWAY_API_VERSION,
        }

        payload = {
            "model": model,
            "promptText": prompt,
            # Vertical short-form output. Runway's accepted ratio strings
            # can change with the API version — if this account/model
            # rejects it, we fall back to the plain frame below rather
            # than failing the whole thumbnail task.
            "ratio": "1080:1920",
            "referenceImages": [
                {"uri": f"data:image/jpeg;base64,{b64}"}
            ],
        }

        create = _requests.post(
            f"{RUNWAY_API_BASE}/text_to_image",
            headers=headers,
            json=payload,
            timeout=30,
        )
        create.raise_for_status()
        task_id = create.json()["id"]

        deadline = time.time() + 180
        output_url = None

        while time.time() < deadline:
            time.sleep(5)

            poll = _requests.get(
                f"{RUNWAY_API_BASE}/tasks/{task_id}",
                headers=headers,
                timeout=30,
            )
            poll.raise_for_status()
            data = poll.json()
            status = data.get("status")

            if status == "SUCCEEDED":
                outputs = data.get("output") or []
                output_url = outputs[0] if outputs else None
                break

            if status in ("FAILED", "CANCELLED"):
                log(
                    f"Runway task {task_id} {status}: "
                    f"{data.get('failure')}"
                )
                return False

        if not output_url:
            log(f"Runway task {task_id} timed out or produced no output")
            return False

        image = _requests.get(output_url, timeout=60)
        image.raise_for_status()
        Path(out_path).write_bytes(image.content)
        return True

    except Exception:
        log(
            "Runway thumbnail generation error:\n"
            + traceback.format_exc()
        )
        return False


def generate_ai_thumbnails(candidate, job, video_path):
    candidate_id = candidate["id"]

    start = float(candidate["start_time"])
    end = float(candidate["end_time"])
    duration = max(0.5, end - start)

    title = (
        candidate.get("manual_title")
        or candidate.get("title")
        or candidate.get("generated_title")
        or "short-form highlight"
    )

    content_type = candidate.get("content_type") or "Reality"

    split_ratio = int(job.get("split_ratio") or 70)

    # Always read from the RAW source video, never a preview/final
    # render — those already have subtitles (and the watermark)
    # burned in, which is why thumbnails used to come out as a plain
    # frame grab with someone else's caption still stuck on it.
    face = detect_face_for_clip(
        video_path, start, end, layout=job.get("layout", "auto")
    )

    source_info = metadata(video_path)

    bottom_pane_height = FINAL_HEIGHT - int(
        FINAL_HEIGHT * split_ratio / 100
    )

    # detect_face_for_clip() returns the raw detected face box
    # (cx/cy/w/h) — calculate_face_crop() is what turns that into an
    # actual x/y/w/h crop rectangle sized for the facecam pane.
    # Passing the raw face dict straight to the frame extractor
    # (which expects "x"/"y") was the bug behind the KeyError: 'x'.
    face_crop = calculate_face_crop(
        source_info["width"],
        source_info["height"],
        face,
        FINAL_WIDTH,
        bottom_pane_height,
    )

    api_key = setting("RUNWAY_API_KEY") or None
    model = setting("RUNWAY_MODEL", "gen4_image_turbo")

    prompt = (
        f"Eye-catching vertical short-form video thumbnail, "
        f"{content_type} mood, high energy, based on the moment: "
        f"{title}. Boost lighting, contrast and color pop, add "
        f"subtle dramatic depth, keep the same subject and "
        f"composition. Do not add any text, letters, or logos — "
        f"this is a background image only. Do not invent or render "
        f"any specific game/brand name; if unsure what the game is, "
        f"just render it as generic stylized gameplay."
    )

    thumbnail_options = []

    for i, fraction in enumerate([0.15, 0.5, 0.85]):

        update_candidate(
            candidate_id,
            progress=10 + i * 28,
            message=f"Generating AI thumbnail {i + 1}/3",
        )

        t = start + max(
            0.0,
            min(duration - 0.05, duration * fraction),
        )

        frame_path = (
            THUMBNAIL_DIR / f"{candidate_id}_frame_{i}.jpg"
        )

        extract_thumbnail_base_frame(
            video_path,
            t,
            face_crop,
            split_ratio,
            FINAL_WIDTH,
            FINAL_HEIGHT,
            frame_path,
        )

        out_path = THUMBNAIL_DIR / f"{candidate_id}_ai_{i}.jpg"
        used_ai = False

        if api_key and frame_path.exists():
            used_ai = runway_generate_image(
                frame_path,
                prompt,
                api_key,
                model,
                out_path,
            )

        if not used_ai:
            out_path.write_bytes(
                frame_path.read_bytes()
            )

        # The actual "designed thumbnail" step: a short, bold,
        # hook-derived headline drawn on top — this is what makes it
        # look like a real thumbnail instead of a still frame.
        compose_thumbnail_headline(out_path, title, content_type)

        thumbnail_options.append(
            str(out_path.relative_to(DATA_ROOT))
        )

    update_candidate(
        candidate_id,
        status="review",
        progress=100,
        message=(
            "AI thumbnails ready"
            if api_key
            else "Thumbnails ready (RUNWAY_API_KEY not configured — using plain frames)"
        ),
        thumbnail_options=json.dumps(thumbnail_options),
    )


# ============================================================
# CLAIM CANDIDATE WORK
# ============================================================

def claim_candidate_task():

    with db() as conn:

        row = conn.execute(
            """
            SELECT
                c.*,
                j.split_ratio,
                j.platform,
                j.subtitle_style,
                j.subtitle_font,
                j.subtitle_size,
                j.subtitle_animation,
                j.layout,
                j.watermark_width,
                j.watermark_opacity,
                j.transcript_segments,
                sv.source_path
            FROM clip_candidates c
            JOIN jobs j
              ON j.id = c.job_id
            JOIN source_videos sv
              ON sv.id = j.source_video_id
            WHERE c.status IN (
                'preview_queued',
                'render_queued',
                'thumbnail_queued'
            )
            ORDER BY c.updated_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ).fetchone()

        if not row:

            return None

        next_status = {
            "preview_queued": "preview_rendering",
            "render_queued": "rendering",
            "thumbnail_queued": "thumbnail_rendering",
        }[row["status"]]

        next_message = {
            "preview_rendering": "Refreshing preview",
            "rendering": "Rendering final",
            "thumbnail_rendering": "Generating AI thumbnails",
        }[next_status]

        conn.execute(
            """
            UPDATE clip_candidates
            SET status = %s,
                progress = 10,
                message = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                next_status,
                next_message,
                row["id"],
            ),
        )

        conn.commit()

    return dict(
        row
    )


# ============================================================
# PROCESS CANDIDATE TASK
# ============================================================

def process_candidate_task(
    task
):

    candidate_id = task["id"]

    stage = task["status"]

    try:

        video_path = Path(
            task["source_path"]
        )

        if not video_path.exists():

            raise RuntimeError(
                "Source video missing: "
                + str(video_path)
            )

        job = {
            "split_ratio":
                task["split_ratio"],

            "subtitle_style":
                task["subtitle_style"],

            "subtitle_font":
                task["subtitle_font"],

            "subtitle_size":
                task["subtitle_size"],

            "subtitle_animation":
                task.get("subtitle_animation"),

            "layout":
                task.get("layout") or "auto",

            "watermark_width":
                task.get("watermark_width"),

            "watermark_opacity":
                task.get("watermark_opacity"),

            "transcript_segments":
                task["transcript_segments"],
        }

        if (
            task["status"]
            == "preview_queued"
        ):

            create_preview(
                task,
                job,
                video_path,
            )

        elif (
            task["status"]
            == "thumbnail_queued"
        ):

            generate_ai_thumbnails(
                task,
                job,
                video_path,
            )

        else:

            update_candidate(
                candidate_id,
                progress=25,
                message=
                    "Rendering approved clip",
            )

            render_final_candidate(
                task,
                job,
                video_path,
            )

            with db() as conn:

                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'completed',
                        progress = 100,
                        message =
                            'Approved Short rendered',
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        task["job_id"],
                    ),
                )

                conn.commit()

            log(
                "FINAL COMPLETE: "
                + str(candidate_id)
            )

    except Exception as exc:

        detail = (
            traceback.format_exc()
        )

        update_candidate(
            candidate_id,

            status="failed",

            message=
                "Candidate processing failed",

            error_stage=
                stage,

            error_message=(
                str(exc)
                + "\n\n"
                + detail[-8000:]
            ),
        )

        log(
            f"CANDIDATE FAILED "
            f"{candidate_id}: "
            f"{exc}"
        )


# ============================================================
# RESET ORPHANS
# ============================================================

def reset_orphans():

    with db() as conn:

        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                message =
                    'Worker restarted mid-job',
                error_stage =
                    'worker_restart',
                error_message =
                    'Worker was restarted while processing',
                updated_at = NOW()
            WHERE status = 'processing'
            """
        )

        conn.execute(
            """
            UPDATE clip_candidates
            SET status = 'failed',
                message =
                    'Worker restarted mid-task',
                error_stage =
                    'worker_restart',
                error_message =
                    'Worker was restarted while processing',
                updated_at = NOW()
            WHERE status IN (
                'preview_rendering',
                'rendering'
            )
            """
        )

        conn.commit()


# ============================================================
# MAIN
# ============================================================

def claim_submagic_task():
    """
    Claims a candidate queued for a Submagic action: upload+transcribe,
    trigger export, or pull down a completed export as the final
    render. Mirrors claim_candidate_task()'s FOR UPDATE SKIP LOCKED
    pattern but on the separate submagic_status column, so it never
    collides with the native preview/render/thumbnail queue.
    """

    with db() as conn:

        row = conn.execute(
            """
            SELECT c.*, sv.source_path,
                   j.watermark_width, j.watermark_opacity,
                   j.split_ratio, j.layout
            FROM clip_candidates c
            JOIN jobs j ON j.id = c.job_id
            JOIN source_videos sv ON sv.id = j.source_video_id
            WHERE c.submagic_status IN (
                'queued_upload',
                'queued_export',
                'queued_apply'
            )
            ORDER BY c.updated_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ).fetchone()

        if not row:
            return None

        next_status = {
            "queued_upload": "uploading",
            "queued_export": "exporting",
            "queued_apply": "applying",
        }[row["submagic_status"]]

        conn.execute(
            """
            UPDATE clip_candidates
            SET submagic_status = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (next_status, row["id"]),
        )

        conn.commit()

        row = dict(row)
        row["submagic_status"] = next_status
        return row


def claim_submagic_poll():
    """
    Picks up a candidate mid-flight on Submagic's side (transcribing
    or exporting) to check on it — throttled to roughly once every 6
    seconds per candidate via the updated_at bump below, so this
    doesn't hammer Submagic's rate limits while idling in the main
    loop.
    """

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM clip_candidates
            WHERE submagic_status IN ('transcribing', 'exporting')
              AND submagic_project_id IS NOT NULL
              AND updated_at < NOW() - INTERVAL '6 seconds'
            ORDER BY updated_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ).fetchone()

        if not row:
            return None

        conn.execute(
            """
            UPDATE clip_candidates
            SET updated_at = NOW()
            WHERE id = %s
            """,
            (row["id"],),
        )

        conn.commit()

        return dict(row)


def _submagic_candidate_title(candidate):

    for key in ("manual_title", "title", "generated_title"):

        value = candidate.get(key)

        if value and str(value).strip():
            return str(value).strip()[:100]

    sub = str(
        candidate.get("subtitle_override")
        or candidate.get("subtitle_text")
        or ""
    ).strip()

    return (sub.split("\n")[0] or "ClipFlow candidate")[:100]


def process_submagic_task(candidate):

    candidate_id = candidate["id"]
    api_key = setting("SUBMAGIC_API_KEY")

    if not api_key:
        update_candidate(
            candidate_id,
            submagic_status="failed",
            submagic_error=(
                "SUBMAGIC_API_KEY is not configured — add it in Settings"
            ),
        )
        return

    action = candidate["submagic_status"]

    try:

        if action == "uploading":

            # R-06: upload a clean plate (no burned-in subtitles, no
            # watermark), not the preview. The preview has our ASS
            # captions baked in, so Submagic's captions doubled up.
            source_path = candidate.get("source_path")

            if not source_path or not Path(source_path).exists():
                raise RuntimeError(
                    "Source video missing: " + str(source_path)
                )

            upload_path = render_clean_plate(
                candidate,
                {
                    "split_ratio": candidate.get("split_ratio"),
                    "layout": candidate.get("layout") or "auto",
                },
                Path(source_path),
            )

            hook_text = _submagic_candidate_title(candidate)

            with open(upload_path, "rb") as fh:

                resp = submagic_request(
                    "POST",
                    "/projects/upload",
                    api_key=api_key,
                    files={
                        "file": (
                            f"{candidate_id}.mp4",
                            fh,
                            "video/mp4",
                        )
                    },
                    data={
                        "title": hook_text,
                        "language": setting(
                            "WHISPER_LANGUAGE"
                        ),
                        "templateName": setting(
                            "SUBMAGIC_TEMPLATE", "Hormozi 2"
                        ),
                        "autoRender": "false",
                        "magicZooms": setting(
                            "SUBMAGIC_MAGIC_ZOOMS", "true"
                        ),
                        "magicBrolls": setting(
                            "SUBMAGIC_MAGIC_BROLLS", "true"
                        ),
                        "hookTitle": json.dumps(
                            {"text": hook_text}
                        ),
                    },
                    timeout=300,
                )

            update_candidate(
                candidate_id,
                submagic_project_id=resp.get("id"),
                submagic_status="transcribing",
                submagic_error=None,
            )

        elif action == "exporting":

            project_id = candidate.get("submagic_project_id")

            if not project_id:
                raise RuntimeError("No Submagic project to export")

            submagic_request(
                "POST",
                f"/projects/{project_id}/export",
                api_key=api_key,
                json={},
            )

            # Status stays "exporting" — claim_submagic_poll() picks up
            # the actual completion.

        elif action == "applying":

            download_url = candidate.get("submagic_download_url")

            if not download_url:
                raise RuntimeError("No completed Submagic render to use")

            output_path = (
                FINAL_DIR / (str(candidate_id) + "_submagic.mp4")
            )

            # Download raw, then burn our watermark on top (R-05):
            # Submagic renders from a clean plate (R-06), and a
            # watermark baked into the upload would be cropped by
            # its Magic Zooms.
            raw_path = (
                FINAL_DIR / (str(candidate_id) + "_submagic_raw.mp4")
            )

            with _requests.get(
                download_url, stream=True, timeout=300
            ) as resp:

                resp.raise_for_status()

                with open(raw_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)

            wm_width, wm_opacity = job_watermark(candidate)

            apply_watermark_overlay(
                raw_path,
                output_path,
                watermark_width=wm_width,
                watermark_opacity=wm_opacity,
            )

            raw_path.unlink(missing_ok=True)

            thumbnail_locked = bool(candidate.get("thumbnail_locked"))
            update_fields = {
                "final_path": str(output_path),
                "status": "completed",
                "progress": 100,
                "message": "Final render completed (Submagic)",
                "submagic_status": "applied",
            }

            if not thumbnail_locked:
                thumb_path = (
                    FINAL_DIR / (str(candidate_id) + "_submagic.jpg")
                )
                create_thumbnail(output_path, thumb_path)
                update_fields["thumbnail_path"] = str(thumb_path)

            update_candidate(candidate_id, **update_fields)

    except Exception as exc:

        log(
            f"Submagic task failed for candidate {candidate_id}: {exc}"
        )

        # An apply that fails should fall back to "completed" (still
        # has a usable Submagic render to retry from), not "failed".
        fallback = "completed" if action == "applying" else "failed"

        update_candidate(
            candidate_id,
            submagic_status=fallback,
            submagic_error=str(exc)[:500],
        )


def process_submagic_poll(candidate):

    candidate_id = candidate["id"]
    api_key = setting("SUBMAGIC_API_KEY")
    project_id = candidate.get("submagic_project_id")

    if not api_key or not project_id:
        return

    try:

        resp = submagic_request(
            "GET",
            f"/projects/{project_id}",
            api_key=api_key,
        )

    except Exception as exc:
        log(f"Submagic poll failed for candidate {candidate_id}: {exc}")
        return

    remote_status = resp.get("status")
    local_status = candidate["submagic_status"]

    if remote_status == "failed":
        update_candidate(
            candidate_id,
            submagic_status="failed",
            submagic_error=(
                resp.get("failureReason") or "Submagic processing failed"
            ),
        )
        return

    if local_status == "transcribing":

        if resp.get("transcriptionStatus") == "COMPLETED":
            update_candidate(
                candidate_id,
                submagic_status="transcribed",
            )

    elif local_status == "exporting":

        if remote_status == "completed":
            update_candidate(
                candidate_id,
                submagic_status="completed",
                submagic_preview_url=resp.get("previewUrl"),
                submagic_download_url=(
                    resp.get("directUrl") or resp.get("downloadUrl")
                ),
            )


def main():




    validate_ai()

    log(
        "AI Video Clipper Worker v4 started"
    )

    log(
        "AI providers: hooks="
        + str(setting("CLIP_ANALYSIS_PROVIDER"))
        + " utility="
        + str(setting("TEXT_UTILITY_PROVIDER"))
        + " health="
        + json.dumps(ai_router.provider_health())
    )

    log(
        "Flow: "
        "download -> normalize -> transcript -> "
        "AI hooks (Gemini/Claude) -> preview -> "
        "human review -> final render"
    )

    log(
        "Final branding: WATERMARK ONLY"
    )

    reset_orphans()

    while True:

        try:

            # User-triggered preview/final render
            # gets priority.
            task = (
                claim_candidate_task()
            )

            if task:

                process_candidate_task(
                    task
                )

                continue

            job = (
                claim_analysis_job()
            )

            if job:

                process_analysis_job(
                    job
                )

                continue

            submagic_task = (
                claim_submagic_task()
            )

            if submagic_task:

                process_submagic_task(
                    submagic_task
                )

                continue

            submagic_poll_row = (
                claim_submagic_poll()
            )

            if submagic_poll_row:

                process_submagic_poll(
                    submagic_poll_row
                )

                continue

            time.sleep(
                2
            )

        except Exception as exc:

            log(
                "Worker loop error: "
                + str(exc)
            )

            time.sleep(
                5
            )


# ============================================================
# TELEGRAM NOTIFICATION
# ============================================================

#def notify_telegram(
#    message
#):

#    if (
#        not TELEGRAM_BOT_TOKEN
#        or not TELEGRAM_CHAT_ID
#    ):

#        return

#    try:

#       _requests.post(
#            (
#                "https://api.telegram.org/"
#                f"bot{TELEGRAM_BOT_TOKEN}/"
#                "sendMessage"
#            ),
#
#            data={
#                "chat_id":
#                    TELEGRAM_CHAT_ID,

#                "text":
#                   message,

#                "parse_mode":
#                    "HTML",
#            },

#            timeout=10,
#        )

#    except Exception as exc:

#        log(
#            "Telegram notify failed: "
#            + str(exc)
#        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()