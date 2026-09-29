"""
One entry point for every AI call in backend and worker:

    ai_generate_json(prompt, schema, *, task, max_tokens) -> parsed JSON

`task` names the call site ("hooks", "new_hook", "subtitle_fix",
"description") for per-task model choice and logging. `schema` is a
JSON Schema of the expected shape (used by providers that can enforce
it). Raises shared.errors.AITransientError / AIPermanentError only.

Each process calls configure() once with its settings getter and log
function (worker: setting()/log(), backend: runtime_setting()/print).
"""

import random
import time

from shared.errors import AIError, classify_exception, is_transient_gemini_error

from . import claude, gemini

PROVIDERS = {gemini.NAME: gemini, claude.NAME: claude}

_setting = None
_log = print


def configure(setting, log=print):
    global _setting, _log
    _setting = setting
    _log = log


def _max_attempts():
    try:
        return max(1, int(float(_setting("GEMINI_MAX_ATTEMPTS"))))
    except (TypeError, ValueError):
        return 4


def ai_generate_json(prompt, schema, *, task, max_tokens, attempts=None,
                     provider="gemini"):
    if _setting is None:
        raise RuntimeError("shared.ai.router.configure() was not called")

    max_attempts = attempts or _max_attempts()

    for attempt in range(1, max_attempts + 1):
        try:
            data, _model = PROVIDERS[provider].generate_json(
                prompt, schema, task=task, max_tokens=max_tokens,
                setting=_setting,
            )
            return data
        except AIError as exc:
            cause = exc.cause if exc.cause is not None else exc
            if (
                not is_transient_gemini_error(cause)
                or attempt >= max_attempts
            ):
                raise
            delay = 2 ** (attempt - 1) + random.uniform(0, 1)
            if provider != "gemini":
                raise
            _log(f"Gemini retry {attempt}/{max_attempts} in {delay:.1f}s")
            time.sleep(delay)


__all__ = ["ai_generate_json", "classify_exception", "configure"]
