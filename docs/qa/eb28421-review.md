# eb28421 (143) worker + notifier wait for a migrated backend — QA 2026-10-07

Verified on production deploy 2026-10-06 21:42Z: backend started 21:42:14, worker and notifier at 21:42:20 (after the
health check passed). All 5 riftstorm-* up, RestartCount 0. Staging mirror f442569 has the same ordering.
Risk (Low): /health is the readiness signal, so it must keep returning 200 only after ensure_schema(). If /health ever
moves ahead of migrations, 143 silently stops protecting the worker.
Docs-only, no review needed: 6bb58c3, c4d4d45, eae2ad8, 3f2f5e4, 5cea31a.
