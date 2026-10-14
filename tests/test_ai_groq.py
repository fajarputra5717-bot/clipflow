"""shared/ai/groq.py (220) with a fake Groq: `python3 -m unittest tests.test_ai_groq`."""
import json
import unittest
from unittest import mock

import requests

from shared.ai import groq
from shared.errors import AINotConfiguredError, AIPermanentError, AIProviderSkip, AITransientError

KEY = "gsk_test_secret_value"
SETTINGS = {"GROQ_API_KEY": KEY, "GROQ_MODEL_ANALYSIS": "openai/gpt-oss-120b", "GROQ_MODEL_UTILITY": "openai/gpt-oss-20b"}
setting = SETTINGS.get

HOOKS = {"type": "array", "items": {"type": "object", "properties": {"start": {"type": "number"}, "title": {"type": "string"},
         "content_type": {"type": "string", "enum": ["funny", "clutch"]}}, "required": ["start", "title", "content_type"]}}
BRIEF = {"type": "object", "properties": {"name": {"type": "string"}, "rate": {"type": "number"},
         "rules": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
                                              "required": ["id"]}}}, "required": ["name"]}


class Resp:
    def __init__(self, status=200, data=None, headers=None, text=None):
        self.status_code, self._data, self.headers = status, data, headers or {}
        self.text = text if text is not None else json.dumps(data or {})

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


def ok(content, finish="stop", model="openai/gpt-oss-120b"):
    return Resp(200, {"model": model, "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": finish}],
                      "usage": {"prompt_tokens": 1200, "completion_tokens": 340}}, {"x-ratelimit-limit-tokens": "250000"})


def err(status, message="x", code="", headers=None):
    return Resp(status, {"error": {"message": message, "code": code}}, headers)


class GroqTest(unittest.TestCase):
    def setUp(self):
        groq._tpm_limit.clear()
        self.sent = []

    def call(self, resp, prompt="Find hooks", schema=HOOKS, task="hooks", max_tokens=16000, images=None):
        def post(url, json=None, timeout=None, headers=None):
            self.sent.append((url, json, headers))
            if isinstance(resp, Exception):
                raise resp
            return resp
        with mock.patch.object(groq.requests, "post", side_effect=post):
            return groq.generate_json(prompt, schema, task=task, max_tokens=max_tokens, setting=setting, images=images)

    def test_hooks_request_is_strict_wrapped_and_keyed_in_the_header_only(self):
        data, model, usage = self.call(ok({"clips": [{"start": 1.5, "title": "A", "content_type": "funny"}]}))
        self.assertEqual(data, [{"start": 1.5, "title": "A", "content_type": "funny"}])
        self.assertEqual((model, usage), ("openai/gpt-oss-120b", {"input": 1200, "output": 340}))
        url, body, headers = self.sent[0]
        self.assertEqual(headers, {"Authorization": f"Bearer {KEY}"})
        self.assertNotIn(KEY, url + json.dumps(body))
        rf = body["response_format"]
        self.assertEqual((rf["type"], rf["json_schema"]["strict"]), ("json_schema", True))
        top = rf["json_schema"]["schema"]
        self.assertEqual((top["required"], top["additionalProperties"]), (["clips"], False))
        self.assertFalse(top["properties"]["clips"]["items"]["additionalProperties"])
        self.assertEqual(body["model"], "openai/gpt-oss-120b")
        self.assertEqual(body["reasoning_effort"], "medium")
        self.assertEqual(body["max_completion_tokens"], 16000 + 4096)
        self.assertIn('one JSON object {"clips": [...]}', body["messages"][0]["content"])   # live: bare arrays failed validation

    def test_utility_uses_the_fast_model(self):
        self.call(ok({"fixed": "ok"}, model="openai/gpt-oss-20b"), schema={"type": "object", "properties": {"fixed": {"type": "string"}},
                                                                            "required": ["fixed"]}, task="subtitle_fix", max_tokens=500)
        body = self.sent[0][1]
        self.assertEqual((body["model"], body["reasoning_effort"], body["max_completion_tokens"]), ("openai/gpt-oss-20b", "low", 1524))

    def test_optional_fields_become_nullable_and_their_nulls_are_dropped(self):
        strict = groq._strict(BRIEF)
        self.assertEqual(strict["required"], ["name", "rate", "rules"])
        self.assertEqual(strict["properties"]["rate"]["type"], ["number", "null"])
        item = strict["properties"]["rules"]["items"]
        self.assertEqual((item["required"], item["properties"]["note"]["type"], item["additionalProperties"]), (["id", "note"], ["string", "null"], False))
        self.assertEqual(BRIEF["required"], ["name"])                          # the caller's schema is untouched
        data, _m, _u = self.call(ok({"name": "Fandra", "rate": None, "rules": [{"id": "r1", "note": None}]}), schema=BRIEF, task="brief")
        self.assertEqual(data, {"name": "Fandra", "rules": [{"id": "r1"}]})

    def test_enum_optional_gets_null(self):
        s = groq._strict({"type": "object", "properties": {"k": {"type": "string", "enum": ["a"]}}})
        self.assertEqual(s["properties"]["k"]["enum"], ["a", None])

    def test_rate_limit_and_too_large_skip_to_the_next_provider(self):
        with self.assertRaises(AIProviderSkip) as e:
            self.call(err(429, "Rate limit reached for model openai/gpt-oss-120b", "rate_limit_exceeded", {"retry-after": "17"}))
        self.assertEqual((e.exception.status, e.exception.retry_after, e.exception.final_transient), (429, 17.0, True))
        with self.assertRaises(AIProviderSkip) as e:
            self.call(err(413, "Request too large for model openai/gpt-oss-120b on tokens per minute (TPM): Limit 8000, Requested 21950"))
        self.assertEqual((e.exception.status, e.exception.final_transient), (413, False))
        self.assertEqual(groq.request_limit("openai/gpt-oss-120b"), 8000)       # learned from the 413

    def test_other_errors(self):
        for resp, cls in ((err(401, "Invalid API Key", "invalid_api_key"), AINotConfiguredError),
                          (err(503, "over capacity"), AITransientError),
                          (err(400, "Generated JSON does not match the expected schema", "json_validate_failed"), AITransientError),
                          (err(400, "schema keyword not supported"), AIProviderSkip),
                          (err(404, "model not found", "model_not_found"), AIProviderSkip),
                          (requests.Timeout("read timed out"), AITransientError),
                          (requests.ConnectionError("refused"), AITransientError)):
            with self.subTest(resp=getattr(resp, "status_code", resp)), self.assertRaises(cls) as e:
                self.call(resp)
            self.assertNotIn(KEY, str(e.exception))
        with self.assertRaises(AIProviderSkip) as e:                              # QA 72c7025 Low: an echoed key is redacted
            self.call(err(400, f"bad request for key {KEY}"))
        self.assertNotIn(KEY, str(e.exception))
        self.assertIn("***", str(e.exception))
        with self.assertRaises(AIPermanentError):
            self.call(ok({"clips": []}, finish="length"))
        with self.assertRaises(AITransientError):
            self.call(Resp(200, {"choices": [{"message": {"content": "{not json"}, "finish_reason": "stop"}]}))

    def test_not_configured_and_images(self):
        with self.assertRaises(AINotConfiguredError):
            groq.generate_json("p", HOOKS, task="hooks", max_tokens=10, setting={}.get)
        with self.assertRaises(AIProviderSkip):
            self.call(ok({}), images=[b"jpeg"])
        self.assertEqual(self.sent, [])

    def test_accepts(self):
        self.assertEqual(groq.accepts("short prompt", task="hooks", max_tokens=16000, setting=setting), (True, ""))
        self.assertFalse(groq.accepts("p", task="edit_moments", max_tokens=800, setting=setting, images=[b"x"])[0])
        big = "x" * 400_000                                                        # the full-transcript cap: ~133K tokens
        okay, why = groq.accepts(big, task="hooks", max_tokens=16000, setting=setting)
        self.assertFalse(okay)
        self.assertIn("131072", why)
        hour = "x" * 75_000                                                        # ~1 h timed transcript ≈ 25K tokens
        self.assertTrue(groq.accepts(hour, task="hooks", max_tokens=16000, setting=setting)[0])
        groq._tpm_limit["openai/gpt-oss-120b"] = 8000                              # free plan TPM
        okay, why = groq.accepts(hour, task="hooks", max_tokens=16000, setting=setting)
        self.assertFalse(okay)
        self.assertIn("> 8000 allowed", why)
        short = "x" * 18_000                                                       # ~6K tokens: fits, the 20K answer budget isn't counted
        self.assertTrue(groq.accepts(short, task="hooks", max_tokens=16000, setting=setting)[0])

    def test_limit_learned_from_headers(self):
        self.call(ok({"clips": []}))
        self.assertEqual(groq.request_limit("openai/gpt-oss-120b"), 250000)       # learned from the header


if __name__ == "__main__":
    unittest.main()
