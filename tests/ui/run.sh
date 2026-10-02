#!/usr/bin/env bash
# One command: tests/ui/run.sh [playwright args]   e.g. tests/ui/run.sh --project=desktop -g island
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules/@playwright/test ] || npm install --no-audit --no-fund --silent
npx playwright install chromium >/dev/null   # no-op when the browser is already cached
exec npx playwright test "$@"
