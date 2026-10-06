# QA review · 8888e67 · 129 P2 part 2: clip_posts + /api/posts
Reviewer: Lane C · 2026-10-06 · `/api/posts/{id}` under the ownership middleware (POST_PATH_RE); `POST /api/posts` checks body ids: the clip must be the caller's via its job (else 404) and the account via `_check_account`; clip_posts carries user_id. Good. Not verified live (P2 gate).
