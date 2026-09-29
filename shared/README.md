Shared Python package, copied into both the backend and worker images
at /app/shared (compose `additional_contexts: shared: ./shared`).

Rebuild tasks R-20 to R-22 recreate `shared/ai/` (router.py, gemini.py, claude.py)
and `shared/errors.py` here. Import as `from shared.ai import router`.
