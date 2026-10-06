# 128 · P2 part 1: posting accounts per user (platform + handle), managed in Settings · main.py, index.html

- **Table `platform_accounts`** (id, `user_id` NOT NULL → users ON DELETE CASCADE, platform = a
  `rule_checks.PLATFORM_LIMITS` key: facebook/instagram/youtube/tiktok/threads/x, handle without "@", note, active,
  created_at); unique per user on (platform, lower(handle)). Owned like jobs: `ACCOUNT_PATH_RE` added to the
  middleware guard, so another user's account id is 404 on every `/api/accounts/{id}…` route.
- **API:** `GET /api/accounts` → `{accounts, platforms:[{slug,name}]}` (own only); `POST` {platform, handle, note}
  (handle 1-64 of A-Z a-z 0-9 . _ -, leading @ stripped; duplicate → 409); `PATCH /{id}` {handle?, note?, active?};
  `DELETE /{id}`. Part 2 (clip_posts) turns delete-with-posts into deactivate so post history stays intact.
- **UI:** Settings → "Posting accounts" for every user (above admin Users): rows with platform, note, Paused tag,
  Pause/Resume, two-step Remove; add form (platform, handle, optional note). Search hides it unless it matches.
- Will be used by part 3 ("Mark posted": account + URL) and part 4 (per-account monthly caps, e.g. IME 2/platform).

**Verified:** prod read-only: admin `GET /api/accounts` → 0 accounts + 6 platforms, anonymous 401, unknown id 404,
unique index present. Harness 68 passed (+ accounts.spec). Create/duplicate/cross-user 404 → staging write checks.
