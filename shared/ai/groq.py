"""
Groq provider (OpenAI-compatible Chat Completions over HTTPS, `requests`, no SDK). One attempt per call: retries and
failover are the router's job. Raises only shared.errors types.

Structured output = response_format json_schema with strict: true (gpt-oss / qwen3 models; checked against
console.groq.com/docs/structured-outputs 2026-10-14). Strict mode needs every object closed and every property
required, so `_strict()` makes optional properties nullable + required and `_drop_nulls()` removes those nulls again:
callers get the same shape as from Gemini/Claude. A top-level array (hooks) is wrapped as {"clips": [...]}.

Limits (console.groq.com/docs/models, /rate-limits, 2026-10-14): 131,072-token context for the models used here;
the account's tokens-per-minute limit (free plan 8K on gpt-oss) caps ONE request's prompt too, so the router asks
`accepts()` first and skips Groq for a prompt that clearly won't fit (estimate = chars / 3; measured ~3.9 for
Indonesian transcript text, so it errs on skipping). The
TPM limit is learned per model from `x-ratelimit-limit-tokens` (and from a 413's "Limit N"). 429 / 413 /
refused key raise AIProviderSkip / AINotConfiguredError: the router moves to the next provider instead of failing the
job. No vision: calls with images skip Groq. GROQ_API_KEY is env-only and only ever sent as the Bearer header.
"""

import copy
import json
import re
import threading

import requests

from shared.errors import (
    AINotConfiguredError,
    AIPermanentError,
    AIProviderSkip,
    AITransientError,
)

NAME = "groq"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 180

_MODEL_SETTING = {"hooks": "GROQ_MODEL_ANALYSIS", "new_hook": "GROQ_MODEL_ANALYSIS", "brief": "GROQ_MODEL_ANALYSIS"}
_UTILITY_MODEL_SETTING = "GROQ_MODEL_UTILITY"

STRICT_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"}
REASONING_MODELS = ("openai/gpt-oss-",)          # accept reasoning_effort low|medium|high
CONTEXT_TOKENS = {}                              # model → context window; default below
DEFAULT_CONTEXT = 131072
MAX_COMPLETION = {"openai/gpt-oss-120b": 65536, "openai/gpt-oss-20b": 65536, "qwen/qwen3.8-27b": 16384}
CHARS_PER_TOKEN = 3.0
REASONING_HEADROOM = {"analysis": 4096, "utility": 1024}

_lock = threading.Lock()
_tpm_limit = {}                                  # model → tokens/minute learned from the API


def is_configured(setting):
    return bool(setting("GROQ_API_KEY"))


def model_for(task, setting):
    return setting(_MODEL_SETTING.get(task, _UTILITY_MODEL_SETTING))


def _kind(task):
    return "analysis" if task in _MODEL_SETTING else "utility"


def estimate_tokens(text):
    return int(len(text or "") / CHARS_PER_TOKEN) + 1


def _completion_budget(model, task, max_tokens):
    return min(MAX_COMPLETION.get(model, 32768), int(max_tokens) + REASONING_HEADROOM[_kind(task)])


def request_limit(model):
    """Prompt tokens one request may send: the learned per-minute limit (Groq answers 413 when the PROMPT alone is
    over it; measured 2026-10-14: 'Limit 8000, Requested 8078' for a ~7.8K-token prompt with a 20K completion
    budget, so the budget isn't counted), else the context window."""
    with _lock:
        tpm = _tpm_limit.get(model)
    return tpm or CONTEXT_TOKENS.get(model, DEFAULT_CONTEXT)


def accepts(prompt, *, task, max_tokens, setting, images=None):
    """(True, "") or (False, reason): checked by the router BEFORE a call (no vision; clearly too big)."""
    if images:
        return False, "no vision model"
    model = model_for(task, setting)
    est = estimate_tokens(prompt)
    ctx = CONTEXT_TOKENS.get(model, DEFAULT_CONTEXT)
    if est + _completion_budget(model, task, max_tokens) > ctx:
        return False, f"~{est} prompt tokens + the answer > the {ctx}-token context of {model}"
    limit = request_limit(model)
    if est > limit:
        return False, f"~{est} prompt tokens > {limit} allowed per request for {model}"
    return True, ""


# ------------------------------------------------------------------ schema

def _strict(schema):
    """Strict-mode schema: every object closed, every property required; optional ones become nullable."""
    schema = copy.deepcopy(schema)

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            props = node.setdefault("properties", {})
            req = set(node.get("required") or [])
            for key, sub in props.items():
                if key not in req and isinstance(sub, dict) and "type" in sub:
                    t = sub["type"]
                    sub["type"] = list(dict.fromkeys((t if isinstance(t, list) else [t]) + ["null"]))
                    if "enum" in sub:
                        sub["enum"] = list(sub["enum"]) + [None]
            node["required"] = list(props)
            node["additionalProperties"] = False
        for sub in (node.get("properties") or {}).values():
            walk(sub)
        if isinstance(node.get("items"), dict):
            walk(node["items"])
        for sub in node.get("anyOf") or []:
            walk(sub)
        for sub in (node.get("$defs") or {}).values():
            walk(sub)

    walk(schema)
    return schema


def _optional_paths(schema):
    """Set of property names that were optional anywhere (their nulls are dropped from the answer)."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                req = set(node.get("required") or [])
                out.update(k for k in (node.get("properties") or {}) if k not in req)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return out


def _drop_nulls(data, optional):
    if isinstance(data, dict):
        return {k: _drop_nulls(v, optional) for k, v in data.items() if not (v is None and k in optional)}
    if isinstance(data, list):
        return [_drop_nulls(v, optional) for v in data]
    return data


def _wrap(schema):
    if schema.get("type") == "array":
        return {"type": "object", "properties": {"clips": schema}, "required": ["clips"]}, True
    return schema, False


# ------------------------------------------------------------------ call

def _learn_limit(model, resp):
    try:
        tpm = int(resp.headers.get("x-ratelimit-limit-tokens") or 0)
    except (TypeError, ValueError):
        tpm = 0
    if not tpm and resp.status_code == 413:
        m = re.search(r"Limit\s+(\d+)", resp.text or "")
        tpm = int(m.group(1)) if m else 0
    if tpm:
        with _lock:
            _tpm_limit[model] = tpm


def _retry_after(resp):
    try:
        return float(resp.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def _error_message(resp):
    try:
        err = resp.json().get("error") or {}
        return str(err.get("message") or "")[:300], str(err.get("code") or "")
    except ValueError:
        return (resp.text or "")[:300], ""


def body_for(prompt, schema, *, model, task, max_tokens):
    wrapped_schema, wrapped = _wrap(schema)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": _completion_budget(model, task, max_tokens), "temperature": 0.6 if _kind(task) == "analysis" else 0.3}
    if model in STRICT_MODELS:
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": f"{task}_result", "strict": True, "schema": _strict(wrapped_schema)}}
        if wrapped:   # the prompt asks for a JSON array; Groq validates AFTER generating, so say where the array goes
            body["messages"][0]["content"] = (prompt.rstrip() + '\n\nOutput format: one JSON object {"clips": [...]} whose '
                                              '"clips" value is exactly the JSON array described above. No bare array.')
    else:   # best effort: JSON mode + the schema in the prompt
        body["response_format"] = {"type": "json_object"}
        body["messages"][0]["content"] = (prompt.rstrip() + "\n\nAnswer with one JSON object matching this JSON Schema:\n"
                                          + json.dumps(wrapped_schema))
    if model.startswith(REASONING_MODELS):
        body["reasoning_effort"] = "medium" if _kind(task) == "analysis" else "low"
    return body, wrapped


def generate_json(prompt, schema, *, task, max_tokens, setting, images=None):
    """(data, model, usage) in the same shape the other providers return."""
    api_key = setting("GROQ_API_KEY")
    if not api_key:
        raise AINotConfiguredError("GROQ_API_KEY is not configured", provider=NAME)
    if images:
        raise AIProviderSkip("Groq has no vision model for this call", provider=NAME, final_transient=False)
    model = model_for(task, setting)
    body, wrapped = body_for(prompt, schema, model=model, task=task, max_tokens=max_tokens)
    try:
        resp = requests.post(API_URL, json=body, timeout=REQUEST_TIMEOUT_SECONDS,
                             headers={"Authorization": f"Bearer {api_key}"})
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise AITransientError(f"Groq: {type(exc).__name__}", provider=NAME, cause=exc) from exc
    except requests.RequestException as exc:
        raise AITransientError(f"Groq: {type(exc).__name__}", provider=NAME, cause=exc) from exc

    _learn_limit(model, resp)
    status = resp.status_code
    if status != 200:
        message, code = _error_message(resp)
        message = message.replace(api_key, "***")   # QA 72c7025 Low: never pass an echoed key on to logs / job errors
        text = f"Groq {status}{f' {code}' if code else ''}: {message}"
        if status == 429:
            raise AIProviderSkip(text, provider=NAME, status=status, retry_after=_retry_after(resp), final_transient=True)
        if status == 413:
            raise AIProviderSkip(text, provider=NAME, status=status, final_transient=False)
        if status in (401, 403):
            raise AINotConfiguredError(f"Groq refused the API key ({status})", provider=NAME, status=status)
        if status == 400 and code == "json_validate_failed":
            raise AITransientError(text, provider=NAME, status=status)
        if status >= 500 or status in (408, 425):
            raise AITransientError(text, provider=NAME, status=status)
        if status == 404 or code == "model_not_found" or status == 400:
            # A request Groq alone rejects (model id, its schema rules) says nothing about the prompt: next provider.
            raise AIProviderSkip(text, provider=NAME, status=status, final_transient=False)
        raise AIPermanentError(text, provider=NAME, status=status)

    try:
        payload = resp.json()
        choice = payload["choices"][0]
        content = choice["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AITransientError("Groq sent an unreadable answer", provider=NAME, cause=exc) from exc
    if choice.get("finish_reason") == "length":
        raise AIPermanentError(f"{model} hit max_completion_tokens={body['max_completion_tokens']} before finishing",
                               provider=NAME)
    try:
        data = json.loads(content)
    except ValueError as exc:
        raise AITransientError(f"{model} returned invalid JSON", provider=NAME, cause=exc) from exc
    data = _drop_nulls(data, _optional_paths(schema))
    if wrapped:
        if not isinstance(data, dict) or not isinstance(data.get("clips"), list):
            raise AITransientError("Groq answer has no 'clips' list", provider=NAME)
        data = data["clips"]
    u = payload.get("usage") or {}
    usage = {"input": u.get("prompt_tokens"), "output": u.get("completion_tokens")}
    return data, payload.get("model") or model, usage
