"""
Gemini provider (google-genai SDK). One attempt per call: retries and
failover are the router's job. Raises only shared.errors types.
"""

import json

from shared.errors import AINotConfiguredError, classify_exception

NAME = "gemini"


def _client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def is_configured(setting):
    return bool(setting("GEMINI_API_KEY"))


def model_for(task, setting):
    # One Gemini model for every task, as in the baseline.
    return setting("GEMINI_ANALYSIS_MODEL")


def generate_json(prompt, schema, *, task, max_tokens, setting):
    """(data, model, usage). Parsed JSON exactly as Gemini returned it (a list for hooks,
    an object elsewhere). `schema` and `max_tokens` are not sent: the
    baseline used only response_mime_type=application/json and adding
    either would change the output (R-20 is a no-behaviour-change
    refactor)."""
    api_key = setting("GEMINI_API_KEY")
    if not api_key:
        raise AINotConfiguredError(
            "GEMINI_API_KEY is not configured", provider=NAME,
        )
    model = model_for(task, setting)
    # Keep a reference: google-genai 2.x closes a Client that is
    # garbage-collected, which breaks a chained _client(...).models call.
    client = _client(api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        m = response.usage_metadata
        usage = {
            "input": getattr(m, "prompt_token_count", None),
            "output": (getattr(m, "candidates_token_count", None) or 0)
            + (getattr(m, "thoughts_token_count", None) or 0),
        }
        return json.loads(response.text), model, usage
    except Exception as exc:
        raise classify_exception(exc, NAME) from exc
