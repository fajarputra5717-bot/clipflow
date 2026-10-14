#!/usr/bin/env bash
# One command: tests/qa/e2e/run.sh   (staging only; lane-c-* user; needs docker access to the staging containers)
# env: QA_USERS_FILE (json {user: password}) or E2E_PASS, E2E_USER (default lane-c-a), E2E_URL, E2E_KEEP=1, E2E_SKIP_FINAL=1, E2E_JOB=<job id> (resume), E2E_OUT, PW_MODULE
set -euo pipefail
cd "$(dirname "$0")"
export PW_MODULE="${PW_MODULE:-$(ls -d /opt/clipflow/tests/ui/node_modules/playwright 2>/dev/null | head -1)}"
exec node staging-e2e.js
