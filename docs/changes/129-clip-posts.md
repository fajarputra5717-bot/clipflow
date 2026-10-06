# 129 · P2 part 2: clip_posts — the post record (manual today; auto-poster + view tracker later) · shared/posts.py, main.py, index.html

- **Table `clip_posts`** (owned: `user_id`; guard `POST_PATH_RE`): candidate_id (→ clip_candidates ON DELETE SET NULL)
  + snapshots job_id / campaign / title, so post and money history survive a deleted job; platform
  (PLATFORM_LIMITS key), account_id (→ platform_accounts ON DELETE RESTRICT), status
  planned|posted|claimed|paid|dropped, source manual|auto, scheduled_for (P2 Schedule), posted_at, url, external_id,
  views + views_at, claimed_at, paid_at, paid_rp (whole IDR), note, error, created/updated_at.
  Unique: (user_id, url); one live post per (clip, account) (`status <> 'dropped'`).
- **Rules = `shared/posts.py`** (pure, shared with the worker for P5): transitions planned→posted→claimed→paid, any
  non-paid → dropped, dropped → planned, paid final; posted+ needs account + url + posted_at; url must be https on
  the platform's domain (subdomains ok, look-alike suffixes refused); paid needs paid_rp. No payout math here
  (Lane B's shared/payouts.py, P3).
- **API:** `GET /api/posts?status&campaign&candidate_id&job_id` (own), `POST /api/posts` (clip must be yours → else
  404; account yours, active, same platform; status planned|posted, posted_at defaults to now), `PATCH /{id}`
  (transition 409; views stamps views_at; claimed/paid stamp their time), `DELETE /{id}` only planned/dropped
  (else 409 "drop it instead"). Deleting an account with posts pauses it instead (Settings says so).
- UI arrives in part 3 (Ready to post / Mark posted).

**Verified:** `python3 -m unittest tests.test_posts` 8 OK; harness 70 passed (+ paused-instead account spec); prod
read-only: `GET /api/posts` `{"posts":[]}`, anonymous 401, unknown id 404, all 5 indexes present. Create /
transitions / cross-user 404 → staging write checks once lane-b has 129.
