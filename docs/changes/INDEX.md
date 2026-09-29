# Change log index

One line per change, newest last. Open the matching
`NNN-<slug>.md` only when you need the reasoning behind a change
you're about to touch.

Format: `NNN · YYYY-MM-DD · title · files touched`

<!-- entries start; append below this line -->
000 · 2026-09-26 · Rebuild baseline after VM loss (v2.1100 code, rebuilt infra + schema) · all (R-01 re-verified 2026-09-29)
001 · 2026-09-29 · R-02 runtime settings: DB→env→default everywhere, 5 s cache, dead settings wired · shared/settings.py, main.py, worker.py, index.html
002 · 2026-09-29 · R-03 X-ClipFlow-Key auth on /api/*, CORS origin list, signed media tokens for img/video · main.py, index.html
003 · 2026-09-29 · Move app folder /opt/riftstorm → /opt/clipflow (project name/volumes unchanged, symlink kept) · scripts/*.sh, CLAUDE.md, START-HERE.md, cron
004 · 2026-09-29 · R-20 AI provider abstraction: one ai_generate_json(), typed transient/permanent errors, no behaviour change · shared/ai/*, shared/errors.py, main.py, worker.py
005 · 2026-09-29 · R-21 Claude provider: strict tool-use structured output, Sonnet 5.5 hooks / Haiku 4.5 utility · shared/ai/claude.py, shared/settings.py
006 · 2026-09-29 · R-22 AI failover: per-task provider gemini|claude|auto (default auto), backoff+jitter, breaker 3→60 s, hook_provider · shared/ai/router.py, main.py, worker.py
007 · 2026-09-29 · R-01 fix: pin opencv <5 (v5 removed readNetFromCaffe; face detection silently fell back on every render) · worker/requirements.txt
