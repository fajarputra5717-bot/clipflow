# 202d39a (lane-b) test: set CAMPAIGNS_DIR before shared.campaigns is imported — QA 2026-10-07

Test-only change. Matches Lane B's note: shared.campaigns reads CAMPAIGNS_DIR once at import, so the env has to be set
first. Main's tests/test_schedule.py keeps the late setdefault (risk only in a mixed full-suite run). Staging suite 127 passed.
Merge: OK.
