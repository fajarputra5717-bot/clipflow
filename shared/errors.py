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
