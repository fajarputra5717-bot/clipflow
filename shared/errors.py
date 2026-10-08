"""
Typed AI errors shared by backend and worker (R-20).

Every provider call raises one of these, never a raw SDK exception, so
retry and failover logic (shared/ai/router.py) can decide on the
*class* of error instead of string-matching each vendor's messages.

    AITransientError  429 / 5xx / overloaded / timeout / connection:
                      worth retrying, and worth failing over.
    AIPermanentError  400 / 401 / 403 / 404 / malformed output / not
                      configured: fails the same way on retry, and a
                      bad prompt fails the same way on the other
                      provider too, so never fail over on it.
"""

import json
import re as _re


class AIError(Exception):

    transient = False

    def __init__(self, message, *, provider=None, status=None, cause=None):
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.cause = cause


class AITransientError(AIError):
    transient = True


class AIPermanentError(AIError):
    transient = False


class AINotConfiguredError(AIPermanentError):
    """Provider has no API key. The router skips it instead of calling."""


# The baseline's gemini_call() retry test, kept verbatim so R-20 does
# not change which Gemini errors are retried.
_GEMINI_RETRY_MARKERS = (
    "429",
    "503",
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
)


def is_transient_gemini_error(exc):
    message = str(exc)
    return any(marker in message for marker in _GEMINI_RETRY_MARKERS)


_TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504, 529}

_TRANSIENT_MARKERS = (
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
    "DEADLINE_EXCEEDED",
    "overloaded",
    "high demand",
    "timed out",
    "timeout",
    "Connection",
)


def _status_of(exc):
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def classify_exception(exc, provider=None):
    """Map any exception from a provider call to AITransientError or
    AIPermanentError. Already-typed errors pass through unchanged."""
    if isinstance(exc, AIError):
        if exc.provider is None:
            exc.provider = provider
        return exc

    status = _status_of(exc)
    # str(exc) unchanged: it ends up in jobs.error_message / HTTP
    # detail exactly as the baseline showed it.
    message = str(exc) or type(exc).__name__

    if isinstance(exc, (json.JSONDecodeError, KeyError, TypeError)):
        return AIPermanentError(
            message,
            provider=provider, status=status, cause=exc,
        )

    if status is not None:
        cls = (
            AITransientError if status in _TRANSIENT_STATUSES
            or status >= 500 else AIPermanentError
        )
        return cls(message, provider=provider, status=status, cause=exc)

    if isinstance(exc, (TimeoutError, ConnectionError)) or any(
        marker.lower() in message.lower() for marker in _TRANSIENT_MARKERS
    ) or is_transient_gemini_error(exc):
        return AITransientError(
            message, provider=provider, status=status, cause=exc,
        )

    return AIPermanentError(
        message, provider=provider, status=status, cause=exc,
    )


# ------------------------------------------------------------
# Job/candidate failure classes (R-15)
# ------------------------------------------------------------
# transient -> retried automatically with backoff (network, rate limit,
#              upstream 5xx, ffmpeg killed for memory, worker restart).
# permanent -> waits for a human (bad/removed video, unsupported media,
#              disk reserve, bugs). Unknown errors default to permanent
#              so nothing loops forever on an unclassified failure.


FAILURE_TRANSIENT = "transient"
FAILURE_PERMANENT = "permanent"

_TRANSIENT_FAILURE_RE = _re.compile(
    r"HTTP Error (403|408|429|5\d\d)"          # yt-dlp / media URLs
    r"|Got error: .*(403|429|5\d\d)"
    r"|timed out|Timeout|Connection (reset|refused|aborted)"
    r"|Temporary failure in name resolution|Network is unreachable"
    r"|IncompleteRead|RemoteDisconnected"
    r"|Cannot allocate memory|Killed|signal 9|MemoryError"  # OOM
    r"|UNAVAILABLE|RESOURCE_EXHAUSTED|overloaded|high demand",
    _re.IGNORECASE,
)

_PERMANENT_FAILURE_RE = _re.compile(
    r"Video unavailable|Private video|This video (is|has been) removed"
    r"|Sign in to confirm your age|is not a valid URL|Unsupported URL"
    r"|Invalid data found|does not contain any stream|Unsupported codec"
    r"|Not enough disk space|removed by disk retention"
    r"|YouTube blocked this download",   # 167: bot check; retry by hand later, never in a loop
    _re.IGNORECASE,
)


def failure_class(exc):
    """FAILURE_TRANSIENT or FAILURE_PERMANENT for any exception raised
    by a job/candidate stage. Typed AI errors decide for themselves;
    everything else is matched on its message (yt-dlp/ffmpeg output)."""
    if isinstance(exc, AIError):
        return FAILURE_TRANSIENT if exc.transient else FAILURE_PERMANENT
    if isinstance(exc, MemoryError):
        return FAILURE_TRANSIENT
    text = f"{type(exc).__name__}: {exc}"
    if _PERMANENT_FAILURE_RE.search(text):
        return FAILURE_PERMANENT
    if isinstance(exc, (TimeoutError, ConnectionError)) or (
        _TRANSIENT_FAILURE_RE.search(text)
    ):
        return FAILURE_TRANSIENT
    return FAILURE_PERMANENT
