"""Live check of the brief_parser AI fallback (one utility-model call via shared.ai.router).

  docker run --rm --network riftstorm_default --env-file /opt/clipflow/.env -e PYTHONPATH=/work \
    -v "$PWD":/work -w /work --entrypoint python riftstorm-worker:latest \
    scripts/brief_ai_check.py tests/fixtures/briefs/english-cpm-sample.txt
Settings come from app_settings (DB) → env, like the worker. Prints the merged rules (no secrets).
"""
import json
import os
import sys
from datetime import date

import psycopg
from psycopg.rows import dict_row

from shared.ai import router
from shared.brief_parser import parse_brief, router_ai
from shared.settings import RuntimeSettings


def load_app_settings():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM app_settings")}


settings = RuntimeSettings(load_app_settings, log=lambda m: None)
router.configure(lambda k, d=None: settings.get(k, d), lambda m: print("[ai]", m, file=sys.stderr))
text = open(sys.argv[1], encoding="utf-8").read()
raw = {}
_call = router_ai()


def ai(prompt, schema):
    raw["answer"] = _call(prompt, schema)
    return raw["answer"]


rules = parse_brief(text, today=date.today(), ai=ai)
if "--raw" in sys.argv:
    print(json.dumps(raw.get("answer"), indent=1, ensure_ascii=False), file=sys.stderr)
print(json.dumps({k: rules[k] for k in rules if k != "unrecognised_lines"}, indent=1, ensure_ascii=False))
