"""shared/ai/router.py failover with fake providers (220: Gemini -> Groq -> Claude): `python3 -m unittest tests.test_ai_router`."""
import unittest
from unittest import mock

from shared.ai import groq as real_groq
from shared.ai import router
from shared.errors import (AINotConfiguredError, AIPermanentError, AIProviderSkip, AITransientError)


class Fake:
    def __init__(self, name, script=None, configured=True, accepts=None):
        self.NAME, self.script, self.configured, self.calls = name, list(script or []), configured, []
        if accepts is not None:
            self.accepts = accepts

    def is_configured(self, setting):
        return self.configured

    def generate_json(self, prompt, schema, *, task, max_tokens, setting, images=None):
        self.calls.append(task)
        step = self.script.pop(0) if self.script else "ok"
        if isinstance(step, Exception):
            raise step
        return {"by": self.NAME}, f"{self.NAME}-model", {"input": 10, "output": 5}


def T(msg="503 busy"):
    return AITransientError(msg, status=503)


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.settings = {"CLIP_ANALYSIS_PROVIDER": "auto", "TEXT_UTILITY_PROVIDER": "auto", "GEMINI_MAX_ATTEMPTS": "2"}
        self.logs = []
        router.configure(self.settings.get, self.logs.append)
        router.breaker = router._Breaker()
        mock.patch.object(router.time, "sleep", lambda s: None).start()
        self.addCleanup(mock.patch.stopall)

    def use(self, gemini, groq, claude):
        self.p = {"gemini": gemini, "groq": groq, "claude": claude}
        mock.patch.dict(router.PROVIDERS, self.p, clear=True).start()

    def gen(self, task="hooks", prompt="p", images=None):
        return router.ai_generate_json(prompt, {}, task=task, max_tokens=100, with_meta=True, images=images)

    def test_order_is_gemini_groq_claude(self):
        self.assertEqual(router.AUTO_ORDER, ("gemini", "groq", "claude"))
        self.use(Fake("gemini", [T(), T()]), Fake("groq"), Fake("claude"))
        data, meta = self.gen()
        self.assertEqual((data["by"], meta["provider"], meta["failed_over"]), ("groq", "groq", True))
        self.assertEqual(len(self.p["gemini"].calls), 2)            # AUTO_ATTEMPTS_PER_PROVIDER, then fail over
        self.assertEqual(self.p["claude"].calls, [])
        self.assertTrue(any("FAILOVER task=hooks gemini -> groq" in l for l in self.logs))

    def test_groq_429_skips_to_claude_without_retrying_and_pauses_groq(self):
        rl = AIProviderSkip("Groq 429 rate_limit_exceeded", status=429, retry_after=30, final_transient=True)
        self.use(Fake("gemini", [T(), T()]), Fake("groq", [rl]), Fake("claude"))
        data, meta = self.gen()
        self.assertEqual(meta["provider"], "claude")
        self.assertEqual(len(self.p["groq"].calls), 1)
        self.assertTrue(router.breaker.is_open("groq"))
        self.assertTrue(any("SKIP task=hooks groq -> claude" in l for l in self.logs))
        self.use(Fake("gemini", [T(), T()]), Fake("groq"), Fake("claude"))   # next call: groq still paused
        self.assertEqual(self.gen()[1]["provider"], "claude")
        self.assertEqual(self.p["groq"].calls, [])

    def test_groq_413_skips_without_pausing(self):
        big = AIProviderSkip("Groq 413 too large", status=413, final_transient=False)
        self.use(Fake("gemini", [T(), T()]), Fake("groq", [big]), Fake("claude"))
        self.assertEqual(self.gen()[1]["provider"], "claude")
        self.assertFalse(router.breaker.is_open("groq"))

    def test_skip_counts_no_breaker_failure(self):
        for _ in range(5):
            self.use(Fake("gemini", [T(), T()]), Fake("groq", [AIProviderSkip("413", status=413, final_transient=False)]), Fake("claude"))
            self.gen()
        self.assertFalse(router.breaker.is_open("groq"))

    def test_up_front_skip_for_a_prompt_groq_cant_take(self):
        self.use(Fake("gemini", [T(), T()]), real_groq, Fake("claude"))
        self.settings.update(GROQ_API_KEY="k", GROQ_MODEL_ANALYSIS="openai/gpt-oss-120b")
        with mock.patch.object(real_groq.requests, "post") as post:
            meta = self.gen(prompt="x" * 400_000)[1]
        post.assert_not_called()
        self.assertEqual(meta["provider"], "claude")
        self.assertTrue(any("skipping groq for task=hooks up front" in l for l in self.logs))

    def test_images_skip_groq(self):
        self.use(Fake("gemini", [T(), T()]), Fake("groq", accepts=lambda *a, **k: (bool(not k.get("images")), "no vision")), Fake("claude"))
        self.assertEqual(self.gen(task="edit_moments", images=[b"jpg"])[1]["provider"], "claude")
        self.assertEqual(self.p["groq"].calls, [])

    def test_forced_groq(self):
        self.settings["CLIP_ANALYSIS_PROVIDER"] = "groq"
        self.use(Fake("gemini"), Fake("groq"), Fake("claude"))
        self.assertEqual(self.gen()[1]["provider"], "groq")
        self.assertEqual(self.p["gemini"].calls, [])
        # forced groq + a call it can't take → the auto chain without it
        self.use(Fake("gemini"), Fake("groq", accepts=lambda *a, **k: (False, "no vision")), Fake("claude"))
        self.assertEqual(self.gen(images=[b"x"])[1]["provider"], "gemini")
        # forced groq, not configured → its own error
        self.use(Fake("gemini"), Fake("groq", [AINotConfiguredError("GROQ_API_KEY is not configured")]), Fake("claude"))
        with self.assertRaises(AINotConfiguredError):
            self.gen()

    def test_skip_with_no_provider_left(self):
        self.settings["CLIP_ANALYSIS_PROVIDER"] = "groq"
        self.use(Fake("gemini"), Fake("groq", [AIProviderSkip("429", status=429, retry_after=5)]), Fake("claude"))
        with self.assertRaises(AITransientError) as e:
            self.gen()
        self.assertNotIsInstance(e.exception, AIProviderSkip)
        self.use(Fake("gemini"), Fake("groq", [AIProviderSkip("413", status=413, final_transient=False)]), Fake("claude"))
        with self.assertRaises(AIPermanentError):
            self.gen()

    def test_refused_groq_key_moves_on_in_auto(self):
        self.use(Fake("gemini", [T(), T()]), Fake("groq", [AINotConfiguredError("Groq refused the API key (401)")]), Fake("claude"))
        self.assertEqual(self.gen()[1]["provider"], "claude")

    def test_unconfigured_groq_is_left_out(self):
        self.use(Fake("gemini", [T(), T()]), Fake("groq", configured=False), Fake("claude"))
        self.assertEqual(self.gen()[1]["provider"], "claude")
        self.assertEqual(self.p["groq"].calls, [])

    def test_permanent_error_still_stops_at_once(self):
        self.use(Fake("gemini", [AIPermanentError("bad request", status=400)]), Fake("groq"), Fake("claude"))
        with self.assertRaises(AIPermanentError):
            self.gen()
        self.assertEqual(self.p["groq"].calls, [])

    def test_breaker_per_provider(self):
        self.use(Fake("gemini", [T()] * 6), Fake("groq", [T()] * 6), Fake("claude"))
        for _ in range(2):
            self.gen()
        self.assertTrue(router.breaker.is_open("gemini"))
        self.assertTrue(router.breaker.is_open("groq"))
        self.assertFalse(router.breaker.is_open("claude"))

    def test_bad_policy_value(self):
        self.settings["TEXT_UTILITY_PROVIDER"] = "openai"
        self.use(Fake("gemini"), Fake("groq"), Fake("claude"))
        self.assertEqual(self.gen(task="description")[1]["provider"], "gemini")
        self.assertTrue(any("is not gemini|groq|claude|auto" in l for l in self.logs))


if __name__ == "__main__":
    unittest.main()
