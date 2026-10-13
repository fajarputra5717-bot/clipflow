# Cross-user sweep, 2026-10-13 (staging a26b041; lane-c-b → lane-c-a's data)

Setup: lane-c-b reset on staging only (user-approved), password changed through the app's own flow and kept only in the uncommitted scratchpad. Targets: lane-c-a's job b0a4ed97…, clip 0a5548a8…, post, source import, account, campaign slug, version/thumbnail index.

## Result: no cross-user finding
- 90 of the 101 operations sent with lane-c-a's IDs (GET first, then POST/PUT/PATCH with schema-generated bodies naming lane-c-a's IDs): 52×404, 9×403, 26×200, 1×400, 1×409, 1×422.
- Every path-param route that names a lane-c-a object answered 404 (or 403 admin routes). The 200s are lane-c-b's OWN data or shared catalogue: `/api/jobs` [], `/api/review/clips`, `/api/publish-queue`, `/api/posts`, `/api/track`, `/api/accounts`, `/api/settings`, `/api/campaigns[/{slug}[/watermark]]`, `/api/auto-import`, `/api/auth/*` own, `/api/system/disk`. A scan of all 16 list/read responses for any of lane-c-a's 25 object IDs (jobs, clips, posts, accounts, imports, watches) + user id + name found nothing.
- Control: the same 12 path-param GETs as lane-c-a: 11×200 (1×404 = thumbnail-options, no options), so the 404s above are ownership, not wrong paths.
- Writes: no lane-c-a job/clip/post/import/user_setting row changed (updated_at check, 30 min window). Not 403/404: `POST /api/auth/tokens` 200 and `POST /api/accounts` 200 (creates lane-c-b's own token/account; both deleted afterwards by lane-c-b), `PUT /api/review/filter` 200, `PUT /api/telegram` 200 (lane-c-b's own), `POST /api/jobs` 400 (my body was not a YouTube link), `POST /api/telegram/test` 409 (no bot), `POST /api/assets/watermarks` 422 (no file).
- `PUT /api/settings` with an admin-only key (VIEW_PULL_DAILY_UNITS = its default) answered 403 for the member.

## Addendum 2026-10-14: the 6 DELETEs (done)
Throwaways created through the app API as lane-c-a (the direct DB insert had been blocked): a job (cached source, 1 clip), a posted post on its clip, a YouTube account, an API token, a watermark asset. lane-c-b then sent all 6 DELETEs at them: assets 404, tokens 404 "Token not found", accounts 404, posts 404, jobs/{job}/candidates/{clip} 404, jobs/{job} 404. A re-read as lane-c-a showed all six items still present. Extra: a *planned* post (the only kind deletable) on an existing clip: lane-c-b DELETE 404, still present, owner DELETE 200. Result: no cross-user delete. Code check: `auth.py:419` deletes tokens with `AND user_id`.
Notes: a posted post can't be deleted by its owner either (409 "history: drop it instead"), so lane-c-b's 404 there is the ownership check winning; the throwaway account is soft-deleted (inactive row remains, by design); an earlier throwaway token vanished because Lane B's restage ran `purge_auth` (sessions + API tokens), not because of the sweep (a controlled re-test: lane-c-b DELETE → 404, DB row intact). No source-import throwaway: there is no create API (rows come from the channel check) and no DELETE route for imports; the existing import id was in the mutation pass (404).
Cleanup: throwaway job (and its clip), post (dropped, then deleted), token, asset deleted by lane-c-a; the planned post deleted; DB check shows 0 leftover throwaway rows (the account is inactive).

## Not done (superseded)
- (superseded by the addendum) **The 6 DELETE operations** (`/api/auth/tokens/{token_id}`, `/api/accounts/{account_id}`, `/api/posts/{post_id}`, `/api/jobs/{job_id}`, `/api/jobs/{job_id}/candidates/{candidate_id}`, `/api/assets/watermarks/{asset_id}`) were not attempted: the instruction was to aim them at throwaway items, and inserting those rows straight into the staging DB was blocked by the permission classifier (not retried by another route).
- Mutation controls: the owner-side 200 for POST/PUT routes was not run, so a 404 on those could in theory be a bad body; 400/422 would have shown.
- Throwaway items created: none, so none to clean up. Cleanup done: lane-c-b's own token and account.
