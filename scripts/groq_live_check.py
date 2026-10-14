"""Groq live checks (220), read-only: hook selection on existing staging jobs' transcripts, no rows written.
Run in a worker image built from this branch, on the staging network:  python scripts/groq_live_check.py <short job> <1h+ job> forced|gemini|long|outage
"""
import json, os, sys, time
sys.path.insert(0, "/app")
import worker as W
from shared.ai import router, gemini, groq
from shared.errors import AITransientError

SHORT, LONG = sys.argv[1], sys.argv[2]
logs = []
orig_log = router._log
router._log = lambda m: (logs.append(m), orig_log(m))

def load(job_id):
    with W.db() as conn:
        j = conn.execute("SELECT transcript_segments, platform, language, campaign FROM jobs WHERE id=%s", (job_id,)).fetchone()
    return j

def run(job_id, policy, label, clip_count=3):
    os.environ["CLIP_ANALYSIS_PROVIDER"] = policy
    W._settings.invalidate()
    j = load(job_id)
    calls = []
    def call(prompt, schema, max_tokens):
        t = time.time()
        raw, meta = router.ai_generate_json(prompt, schema, task="hooks", max_tokens=max_tokens, with_meta=True)
        calls.append({"chars": len(prompt), "s": round(time.time() - t, 1), **meta})
        return raw, meta
    t0 = time.time(); n = len(logs)
    try:
        hooks, _ = W.select_hooks(j["transcript_segments"], j["platform"] or "youtube_shorts", clip_count,
                                  (W.setting_int("CLIP_TARGET_DURATION"), W.setting_int("CLIP_MIN_DURATION"), W.setting_int("CLIP_MAX_DURATION")),
                                  call, W.languages.job_language(None, j["language"]), None)
        valid = [h for h in hooks if h["end"] > h["start"]]
        res = {"label": label, "ok": True, "clips": len(valid), "secs": round(time.time() - t0, 1),
               "calls": [{k: c[k] for k in ("provider", "model", "chars", "s", "usage", "failed_over")} for c in calls],
               "sample": [(round(h["start"]), round(h["end"]), h["title"][:40]) for h in valid[:3]]}
    except Exception as exc:
        res = {"label": label, "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}", "secs": round(time.time() - t0, 1)}
    res["router_log"] = [l[:170] for l in logs[n:]]
    print("RESULT " + json.dumps(res, ensure_ascii=False), flush=True)
    return res

def wait_minute():
    time.sleep(62)

which = sys.argv[3]
if which == "forced":
    for p in ("gemini", "groq", "claude"):
        run(SHORT, p, f"forced {p}, short"); wait_minute() if p == "groq" else None
elif which == "gemini":
    run(SHORT, "gemini", "forced gemini, short")
elif which == "long":
    run(LONG, "groq", "forced groq, 1h+ transcript")
    wait_minute()
    run(LONG, "auto", "auto, 1h+ transcript")
elif which == "outage":
    real = gemini.generate_json
    def down(*a, **k):
        raise AITransientError("503 UNAVAILABLE (simulated Gemini outage)", status=503)
    gemini.generate_json = down
    router.breaker = router._Breaker()
    r1 = run(SHORT, "auto", "auto, Gemini down → expect Groq")
    for i in range(2, 6):
        r = run(SHORT, "auto", f"auto, Gemini down, call {i} in the same minute (expect a real 429 → Claude)")
        if r.get("calls") and r["calls"][-1]["provider"] == "claude":
            break
    gemini.generate_json = real
