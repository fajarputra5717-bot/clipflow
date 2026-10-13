# 4a20c78 (199) — P5 parts 2+3: Instagram + Facebook view pulls (main, deployed)

Result: **PASS (conditional)** — no High/Medium found; live Meta behaviour unverified (no token). Staging was not restaged to 4a20c78 (lane-b a26b041 only; restaging restarts containers, which Lane C does not do), so the staging checks below are code-level only.

## Verified
- Prod after deploy: backend/worker/sender running, restarts=0 (started 06:20 UTC), frontend/notifier/pot/postgres unchanged, 0 restarts.
- `tests.test_view_pull`: 8/8 OK (git-served 4a20c78).
- META_ACCESS_TOKEN: in `USER_SETTING_KEYS`, `USER_ONLY_KEYS`, `SECRET_SETTING_KEYS`. Code path: member PUT → `set_user_setting` (main.py ~6497), never `app_settings`; GET returns `••••••••` + `scope:user`; `resolve()` returns default for USER_ONLY with no DB/env fallback (settings.py:239-250); `pull_meta_views` reads `user_settings` directly (joined to active users), so an admin's app_settings value is ignored and users cannot read each other's token.
- Token only in `Authorization` header (`_MetaClient.get`), paging via `after` cursor not `paging.next`; the Telegram note and `views_error` carry only Meta's message, not the token.
- YouTube quota sum restricted to `platform='youtube'`; island title "Instagram & Facebook" (main.py list_activity).
- Refused token (190/102/10/2xx → key) is not retried with the same `token_hash`; one note in the member's own chat.

## Findings (all Low)
1. **FB metrics sent as one comma list** (worker.py `_pull_meta_user`, `FB_METRICS`): if either name is invalid for a video Graph usually answers 400 code 100 for the whole call → every Facebook post gets `views_error` "Facebook: HTTP 400…" and never a count. The doc itself says which metric matches is UNCONFIRMED. Fix idea: on a code-100 reply retry each metric alone.
2. **Per-object permission errors read as a dead token**: `meta_error_kind` maps code 10 and 200–299 to `key`. Those can come from a single media/Page the token cannot read; a `key` aborts the whole user run, shows "Meta refused your token" and blocks all pulls until a new token is saved. Consider `key` only for 190/102 and treating 10/2xx on a per-post call as `request`.
3. A non-Meta exception inside one user's run (e.g. DB error) propagates after the `finally` row update and skips remaining users until the next pass (VIEW_PULL_EVERY_S). Cosmetic at current volume.

## Not verified
- Any real Graph call (token scopes, `/me/accounts` shape, `views` insights on IG, `video_reels`/`video_insights` on FB, Bearer header acceptance).
- Live staging PUT/GET of META_ACCESS_TOKEN and the island item (needs restage to 4a20c78); publish "from Instagram / Facebook" wording only via Lane A's UI spec.
- Telegram note delivery.
