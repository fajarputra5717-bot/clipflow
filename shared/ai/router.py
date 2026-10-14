"""
One entry point for every AI call in backend and worker:

    ai_generate_json(prompt, schema, *, task, max_tokens) -> parsed JSON

`task` names the call site ("hooks", "new_hook", "subtitle_fix",
"description") for per-task provider/model choice and logging.
`schema` is a JSON Schema of the expected shape. Raises
shared.errors.AITransientError / AIPermanentError only.

Failover policy (R-22):
- Provider per task group, setting in {gemini, groq, claude, auto}:
    CLIP_ANALYSIS_PROVIDER  -> hooks, new_hook
    TEXT_UTILITY_PROVIDER   -> subtitle_fix, description (and any other task)
  auto = Gemini -> Groq -> Claude (220), next one on transient errors. A
  provider without an API key (or with a refused one) is skipped.
- Up-front fit (220): a provider module may define accepts(); Groq says no
  to calls with images and to prompts clearly over its per-request token
  limit, so it is left out of the chain for that call (a forced provider
  that can't take the call falls back to the auto chain, logged).
- AIProviderSkip (Groq 429 rate limit / 413 too large): no retries, no
  breaker failure; the provider is left alone for retry-after seconds and
  the next one is tried. With no provider left: 429 -> transient (the job
  retries later), 413 -> permanent.
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

from shared.errors import (
    AIError,
    AINotConfiguredError,
    AIPermanentError,
    AIProviderSkip,
    AITransientError,
)

from . import claude, gemini, groq

PROVIDERS = {gemini.NAME: gemini, groq.NAME: groq, claude.NAME: claude}
AUTO_ORDER = (gemini.NAME, groq.NAME, claude.NAME)
SKIP_PAUSE_CAP_SECONDS = 3600

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

    def pause(self, name, seconds):
        """Leave a provider alone for `seconds` (a 429's retry-after) without counting a failure."""
        with self._lock:
            until = time.monotonic() + max(0.0, min(seconds, SKIP_PAUSE_CAP_SECONDS))
            self._open_until[name] = max(self._open_until.get(name, 0.0), until)

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
    if value not in (*PROVIDERS, "auto"):
        _log(f"AI: {key}={value!r} is not {'|'.join(PROVIDERS)}|auto; using auto")
        value = "auto"
    return value


def _int_setting(key, fallback):
    try:
        return max(1, int(float(_setting(key))))
    except (TypeError, ValueError):
        return fallback


def _fits(name, call):
    """(True, "") unless the provider says up front it can't take this call."""
    accepts = getattr(PROVIDERS[name], "accepts", None)
    if not accepts or not call:
        return True, ""
    return accepts(call["prompt"], task=call["task"], max_tokens=call["max_tokens"],
                   setting=_setting, images=call.get("images"))


def _candidates(policy, call=None):
    if policy != "auto":
        ok, why = _fits(policy, call)
        if ok:
            return [policy]
        _log(f"AI: {policy} can't take task={call['task']} ({why}); using the auto chain without it")
    configured = [
        name for name in AUTO_ORDER
        if PROVIDERS[name].is_configured(_setting) and name != (policy if policy != "auto" else None)
    ]
    fitting = []
    for name in configured:
        ok, why = _fits(name, call)
        if ok:
            fitting.append(name)
        else:
            _log(f"AI: skipping {name} for task={call['task']} up front: {why}")
    configured = fitting or configured[:1] or []
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
                     with_meta=False, images=None):
    """See _generate. A FORCED provider that answers AIProviderSkip (Groq 429/413: rate limit, too large; the
    up-front check can't know the account limit before the first reply) falls back to the auto chain without it,
    like an up-front skip (220)."""
    try:
        return _generate(prompt, schema, task=task, max_tokens=max_tokens, attempts=attempts,
                         with_meta=with_meta, images=images)
    except _ForcedSkip as skip:
        _log(f"AI: forced {skip.name} can't take task={task} ({str(skip.error)[:140]}); using the auto chain without it")
        return _generate(prompt, schema, task=task, max_tokens=max_tokens, attempts=attempts,
                         with_meta=with_meta, images=images, exclude=skip.name)


class _ForcedSkip(Exception):
    def __init__(self, name, error):
        super().__init__(str(error))
        self.name, self.error = name, error


def _generate(prompt, schema, *, task, max_tokens, attempts=None,
              with_meta=False, images=None, exclude=None):
    """Parsed JSON; with_meta=True returns (data, meta) where meta =
    {"provider", "model", "failed_over", "usage"}. `attempts` overrides the
    per-provider attempt count (backend handlers pass 1 so a request
    doesn't block on backoff). `images` = optional list of JPEG bytes sent
    with the prompt (vision-capable models only; Auto Edit E1)."""
    if _setting is None:
        raise RuntimeError("shared.ai.router.configure() was not called")

    policy = _policy(task)
    forced = policy != "auto" and not exclude
    if exclude:
        policy = "auto"
    candidates = _candidates(policy, {"prompt": prompt, "task": task, "max_tokens": max_tokens, "images": images})
    if exclude:
        candidates = [n for n in candidates if n != exclude] or [n for n in AUTO_ORDER if n != exclude][:1]
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
                extra = {"images": images} if images else {}
                data, model, usage = module.generate_json(
                    prompt, schema, task=task, max_tokens=max_tokens,
                    setting=_setting, **extra,
                )
            except AINotConfiguredError as exc:
                last_error = exc
                if policy != "auto" and len(candidates) == 1:
                    raise
                _log(f"AI: {name} not usable ({str(exc)[:120]}), next provider")
                break
            except AIProviderSkip as exc:
                last_error = exc
                if exc.retry_after:
                    breaker.pause(name, exc.retry_after)
                if is_last_provider and forced and len(candidates) == 1:
                    raise _ForcedSkip(name, exc) from exc
                if is_last_provider:
                    _log(f"AI: {name} can't take task={task} and no provider is left: {str(exc)[:160]}")
                    cls = AITransientError if exc.final_transient else AIPermanentError
                    raise cls(str(exc), provider=name, status=exc.status, cause=exc) from exc
                _log(
                    f"AI: SKIP task={task} {name} -> {candidates[index + 1]}"
                    f" ({exc.status or ''} {str(exc)[:160]})"
                    + (f"; leaving {name} alone {exc.retry_after:.0f}s" if exc.retry_after else "")
                )
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
