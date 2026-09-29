"""
Claude provider (anthropic SDK, Messages API). One attempt per call:
retries and failover are the router's job. Raises only shared.errors
types.

Structured output = tool use: the call site's JSON Schema becomes a
strict tool's input_schema and the answer is the tool_use block's
input. The tool is forced (tool_choice type "tool") where the model
accepts it. Claude Sonnet 5.5 / Opus 5.5 / Fable 5.1 reject forced
tool_choice with a 400: for those we send tool_choice "auto" plus an
explicit instruction, and strict: true still guarantees the schema.
A model that 400s on forced tool_choice is remembered per process.
"""

import copy

from shared.errors import (
    AINotConfiguredError,
    AIPermanentError,
    AITransientError,
    classify_exception,
)

NAME = "claude"

TOOL_NAME = "emit_result"

# task -> which model setting it uses. Hook selection is the product
# differentiator (Sonnet); fix-typo/description are mechanical (Haiku).
_MODEL_SETTING = {
    "hooks": "CLAUDE_MODEL_ANALYSIS",
    "new_hook": "CLAUDE_MODEL_ANALYSIS",
}
_UTILITY_MODEL_SETTING = "CLAUDE_MODEL_UTILITY"

# Server-side refusal fallback (beta): route a safety refusal to
# another model instead of failing. Only these models accept it.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5",
                    "claude-fable-5-1")

_no_forced_tool_choice = set()

REQUEST_TIMEOUT_SECONDS = 240


def is_configured(setting):
    return bool(setting("ANTHROPIC_API_KEY"))


def model_for(task, setting):
    return setting(_MODEL_SETTING.get(task, _UTILITY_MODEL_SETTING))


def _strict(schema):
    """additionalProperties: false on every object (strict tools need it)."""
    schema = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return schema


def _tool_schema(schema):
    """Tool input must be an object: wrap a top-level array (hooks)
    as {"clips": [...]}. Returns (input_schema, wrapped)."""
    if schema.get("type") == "array":
        return {
            "type": "object",
            "properties": {"clips": schema},
            "required": ["clips"],
        }, True
    return schema, False


def _request(client, model, prompt, tool, max_tokens, forced):
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        tools=[tool],
        messages=[{"role": "user", "content": prompt}],
    )
    if forced:
        kwargs["tool_choice"] = {"type": "tool", "name": TOOL_NAME}
    else:
        kwargs["tool_choice"] = {"type": "auto"}
        kwargs["messages"] = [{
            "role": "user",
            "content": (
                prompt.rstrip()
                + f"\n\nReturn your answer by calling the {TOOL_NAME} "
                "tool exactly once. Do not answer in plain text."
            ),
        }]
    if model.startswith(_FALLBACK_MODELS):
        return client.beta.messages.create(
            betas=[_FALLBACK_BETA],
            extra_body={"fallbacks": "default"},
            **kwargs,
        )
    return client.messages.create(**kwargs)


def _rejects_forced(exc):
    return (
        getattr(exc, "status_code", None) == 400
        and "tool_choice" in str(exc)
    )


def generate_json(prompt, schema, *, task, max_tokens, setting):
    api_key = setting("ANTHROPIC_API_KEY")
    if not api_key:
        raise AINotConfiguredError(
            "ANTHROPIC_API_KEY is not configured", provider=NAME,
        )
    model = model_for(task, setting)

    import anthropic

    # SDK retries off: the router owns retry/backoff/failover.
    client = anthropic.Anthropic(
        api_key=api_key,
        max_retries=0,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    input_schema, wrapped = _tool_schema(schema)
    tool = {
        "name": TOOL_NAME,
        "description": f"Return the {task} result in the required shape.",
        "input_schema": _strict(input_schema),
        "strict": True,
    }

    try:
        forced = model not in _no_forced_tool_choice
        try:
            response = _request(client, model, prompt, tool, max_tokens,
                                forced)
        except anthropic.BadRequestError as exc:
            if not (forced and _rejects_forced(exc)):
                raise
            _no_forced_tool_choice.add(model)
            response = _request(client, model, prompt, tool, max_tokens,
                                False)
    except anthropic.APIConnectionError as exc:
        # Includes APITimeoutError.
        raise AITransientError(str(exc), provider=NAME, cause=exc) from exc
    except Exception as exc:
        raise classify_exception(exc, NAME) from exc

    if response.stop_reason == "refusal":
        raise AIPermanentError(
            f"{model} refused the request", provider=NAME,
        )
    if response.stop_reason == "max_tokens":
        raise AIPermanentError(
            f"{model} hit max_tokens={max_tokens} before finishing",
            provider=NAME,
        )

    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            data = block.input
            if wrapped:
                if not isinstance(data, dict) or "clips" not in data:
                    raise AIPermanentError(
                        "tool input has no 'clips'", provider=NAME,
                    )
                data = data["clips"]
            return data, getattr(response, "model", None) or model

    # tool_choice "auto" does not guarantee a call; a retry usually
    # gets one, so this is transient rather than a bad prompt.
    raise AITransientError(
        f"{model} answered without calling {TOOL_NAME}", provider=NAME,
    )
