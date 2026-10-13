# Cross-user sweep, 2026-10-13 (staging a26b041; lane-c-b → lane-c-a's data)

Setup: lane-c-b reset on staging only (user-approved), password changed through the app's own flow and kept only in the uncommitted scratchpad. Targets: lane-c-a's job b0a4ed97…, clip 0a5548a8…, post, source import, account, campaign slug, version/thumbnail index.

## Result: no cross-user finding
- 90 of the 101 operations sent with lane-c-a's IDs (GET first, then POST/PUT/PATCH with schema-generated bodies naming lane-c-a's IDs): 52×404, 9×403, 26×200, 1×400, 1×409, 1×422.
- Every path-param route that names a lane-c-a object answered 404 (or 403 admin routes). The 200s are lane-c-b's OWN data or shared catalogue: `/api/jobs` [], `/api/review/clips`, `/api/publish-queue`, `/api/posts`, `/api/track`, `/api/accounts`, `/api/settings`, `/api/campaigns[/{slug}[/watermark]]`, `/api/auto-import`, `/api/auth/*` own, `/api/system/disk`. A scan of all 16 list/read responses for any of lane-c-a's 25 object IDs (jobs, clips, posts, accounts, imports, watches) + user id + name found nothing.
- Control: the same 12 path-param GETs as lane-c-a: 11×200 (1×404 = thumbnail-options, no options), so the 404s above are ownership, not wrong paths.
- Writes: no lane-c-a job/clip/post/import/user_setting row changed (updated_at check, 30 min window). Not 403/404: `POST /api/auth/tokens` 200 and `POST /api/accounts` 200 (creates lane-c-b's own token/account; both deleted afterwards by lane-c-b), `PUT /api/review/filter` 200, `PUT /api/telegram` 200 (lane-c-b's own), `POST /api/jobs` 400 (my body was not a YouTube link), `POST /api/telegram/test` 409 (no bot), `POST /api/assets/watermarks` 422 (no file).
- `PUT /api/settings` with an admin-only key (VIEW_PULL_DAILY_UNITS = its default) answered 403 for the member.

## Not done
- **The 6 DELETE operations** (`/api/auth/tokens/{token_id}`, `/api/accounts/{account_id}`, `/api/posts/{post_id}`, `/api/jobs/{job_id}`, `/api/jobs/{job_id}/candidates/{candidate_id}`, `/api/assets/watermarks/{asset_id}`) were not attempted: the instruction was to aim them at throwaway items, and inserting those rows straight into the staging DB was blocked by the permission classifier (not retried by another route).
- Mutation controls: the owner-side 200 for POST/PUT routes was not run, so a 404 on those could in theory be a bad body; 400/422 would have shown.
- Throwaway items created: none, so none to clean up. Cleanup done: lane-c-b's own token and account.
