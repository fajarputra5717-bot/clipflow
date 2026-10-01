"""
One entry point for every AI call in backend and worker:

    ai_generate_json(prompt, schema, *, task, max_tokens) -> parsed JSON

`task` names the call site ("hooks", "new_hook", "subtitle_fix",
"description") for per-task provider/model choice and logging.
`schema` is a JSON Schema of the expected shape. Raises
shared.errors.AITransientError / AIPermanentError only.

Failover policy (R-22):
- Provider per task group, setting in {gemini, claude, auto}:
    CLIP_ANALYSIS_PROVIDER  -> hooks, new_hook
    TEXT_UTILITY_PROVIDER   -> subtitle_fix, description
  auto = Gemini first, Claude on transient errors. A provider without
  an API key is skipped.
- Retries per provider with exponential backoff + jitter, capped at
  BACKOFF_CEILING_SECONDS. Single provider: GEMINI_MAX_ATTEMPTS
  attempts. auto: AUTO_ATTEMPTS_PER_PROVIDER, then fail over.
- Fail over on AITransientError only. AIPermanentError (bad request,
  malformed output, refusal) is raised at once: it would fail the
  same way on the other provider.
- Circuit breaker per provider, per process: 3 consecutive transient
  failures -> skip it for 60 s. If every candidate is open, the one
  whose cooldown ends first is tried anyway (half-open probe) rather
  than failing without a call.

Each process calls configure() once with its settings getter and log
function (worker: setting()/log(), backend: runtime_setting()/print).
"""

import random
import threading
import time

from shared.errors import AIError, AINotConfiguredError, AITransientError

from . import claude, gemini

PROVIDERS = {gemini.NAME: gemini, claude.NAME: claude}
AUTO_ORDER = (gemini.NAME, claude.NAME)

TASK_PROVIDER_SETTING = {
    "hooks": "CLIP_ANALYSIS_PROVIDER",
    "new_hook": "CLIP_ANALYSIS_PROVIDER",
    "subtitle_fix": "TEXT_UTILITY_PROVIDER",
    "description": "TEXT_UTILITY_PROVIDER",
}

AUTO_ATTEMPTS_PER_PROVIDER = 2
BACKOFF_CEILING_SECONDS = 20.0
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 60.0

_setting = None
_log = print


def configure(setting, log=print):
    global _setting, _log
    _setting = setting
    _log = log


# ------------------------------------------------------------
# Circuit breaker
# ------------------------------------------------------------

class _Breaker:

    def __init__(self):
        self._lock = threading.Lock()
        self._failures = {}
        self._open_until = {}

    def open_until(self, name):
        with self._lock:
            return self._open_until.get(name, 0.0)

    def is_open(self, name):
        return self.open_until(name) > time.monotonic()

    def success(self, name):
        with self._lock:
            self._failures[name] = 0
            self._open_until.pop(name, None)

    def failure(self, name):
        with self._lock:
            count = self._failures.get(name, 0) + 1
            self._failures[name] = count
            if count >= BREAKER_THRESHOLD:
                self._open_until[name] = (
                    time.monotonic() + BREAKER_COOLDOWN_SECONDS
                )
                self._failures[name] = 0
                return True
            return False


breaker = _Breaker()


def provider_health():
    """{name: {"configured", "circuit_open_for_s"}} for logs/UI."""
    now = time.monotonic()
    return {
        name: {
            "configured": module.is_configured(_setting),
            "circuit_open_for_s": max(
                0, round(breaker.open_until(name) - now)
            ),
        }
        for name, module in PROVIDERS.items()
    }


# ------------------------------------------------------------
# Policy
# ------------------------------------------------------------

def _policy(task):
    key = TASK_PROVIDER_SETTING.get(task, "TEXT_UTILITY_PROVIDER")
    value = str(_setting(key) or "auto").strip().lower()
    if value not in ("gemini", "claude", "auto"):
        _log(f"AI: {key}={value!r} is not gemini|claude|auto; using auto")
        value = "auto"
    return value


def _int_setting(key, fallback):
    try:
        return max(1, int(float(_setting(key))))
    except (TypeError, ValueError):
        return fallback


def _candidates(policy):
    if policy != "auto":
        return [policy]
    configured = [
        name for name in AUTO_ORDER
        if PROVIDERS[name].is_configured(_setting)
    ]
    # Nothing configured: try the default so the caller gets the
    # provider's own "not configured" error.
    if not configured:
        return [AUTO_ORDER[0]]
    closed = [name for name in configured if not breaker.is_open(name)]
    if closed:
        return closed
    return [min(configured, key=breaker.open_until)]


def _backoff(attempt):
    return min(
        BACKOFF_CEILING_SECONDS, 2 ** (attempt - 1)
    ) + random.uniform(0, 1)


def ai_generate_json(prompt, schema, *, task, max_tokens, attempts=None,
                     with_meta=False):
    """Parsed JSON; with_meta=True returns (data, meta) where meta =
    {"provider", "model", "failed_over", "usage"}. `attempts` overrides the
    per-provider attempt count (backend handlers pass 1 so a request
    doesn't block on backoff)."""
    if _setting is None:
        raise RuntimeError("shared.ai.router.configure() was not called")

    policy = _policy(task)
    candidates = _candidates(policy)
    per_provider = attempts or (
        AUTO_ATTEMPTS_PER_PROVIDER if policy == "auto"
        else _int_setting("GEMINI_MAX_ATTEMPTS", 4)
    )

    last_error = None

    for index, name in enumerate(candidates):
        module = PROVIDERS[name]
        is_last_provider = index == len(candidates) - 1

        for attempt in range(1, per_provider + 1):
            if breaker.is_open(name) and len(candidates) > 1:
                _log(f"AI: {name} circuit open, skipping for task={task}")
                break
            try:
                data, model, usage = module.generate_json(
                    prompt, schema, task=task, max_tokens=max_tokens,
                    setting=_setting,
                )
            except AINotConfiguredError as exc:
                last_error = exc
                if policy != "auto":
                    raise
                break
            except AIError as exc:
                last_error = exc
                if not exc.transient:
                    _log(
                        f"AI: {name} permanent error on task={task}: "
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )
                    raise
                if breaker.failure(name):
                    _log(
                        f"AI: {name} circuit OPEN for "
                        f"{BREAKER_COOLDOWN_SECONDS:.0f}s after "
                        f"{BREAKER_THRESHOLD} consecutive transient errors"
                    )
                if attempt < per_provider and not breaker.is_open(name):
                    delay = _backoff(attempt)
                    _log(
                        f"AI: {name} retry {attempt}/{per_provider} "
                        f"task={task} in {delay:.1f}s "
                        f"({type(exc).__name__}: {str(exc)[:120]})"
                    )
                    time.sleep(delay)
                    continue
                if not is_last_provider:
                    _log(
                        f"AI: FAILOVER task={task} {name} -> "
                        f"{candidates[index + 1]} after {attempt} "
                        f"attempt(s), error={type(exc).__name__}"
                        f"{f' {exc.status}' if exc.status else ''}: "
                        f"{str(exc)[:160]}"
                    )
                break
            else:
                breaker.success(name)
                if index > 0:
                    _log(f"AI: task={task} served by {name} ({model}) "
                         "after failover")
                meta = {
                    "provider": name,
                    "model": model,
                    "failed_over": index > 0,
                    # {"input", "output"} tokens; output includes thinking.
                    "usage": usage,
                }
                return (data, meta) if with_meta else data

    if last_error is None:
        last_error = AITransientError(
            f"No AI provider available for task={task}"
        )
    raise last_error
