# 167 · yt-dlp vs YouTube's "Sign in to confirm you're not a bot" (2026-10-09)

**Found:** last prod imports (≤ 2026-10-06) downloaded fine; on 2026-10-09 a fresh download from this server hit the
bot check (yt-dlp 2026.08.19 = latest). Tested clients: web / tv / android_vr / tv_simply → bot check or error;
bgutil PO token alone (web) → still blocked; **mweb + bgutil PO token → full formats (1080p avc1 + m4a)**; mweb
without a PO token drops the https formats.

- `shared/ytdlp.py` = the one place for yt-dlp calls (worker now, Lane B's source_watch next): `base_args()` (client +
  PO-token URL), `wait_turn()` (YTDLP_MIN_GAP_SECONDS, default 20 s + ≤ 30 % jitter, flock'd timestamp in
  /data/.ytdlp-last-call so every process shares it), `is_bot_check()`, `cookies_args()`.
- New compose service `pot` (brainicism/bgutil-ytdlp-pot-provider:2.0.2, internal only); worker pip
  `bgutil-ytdlp-pot-provider==2.0.2`; `yt-dlp[default]==2026.8.19` pinned. **Monthly:** bump both pins, rebuild
  worker + sender, run the download check below.
- Cookies: optional `secrets/youtube-cookies.txt` (gitignored dir, mounted read-only at /run/secrets/clipflow), path =
  setting YTDLP_COOKIES_FILE. Used ONLY to retry once after a bot check (temp copy, deleted after).
- Bot check that survives → job fails **permanent** with "YouTube blocked this download (bot check). Retry in about an
  hour…" (no auto-retry loop) + Telegram line to the admin chat (≤ 1/hour per process).
- Settings: YTDLP_PLAYER_CLIENT (mweb), YTDLP_POT_URL (http://pot:4416; empty = off), YTDLP_MIN_GAP_SECONDS (20),
  YTDLP_COOKIES_FILE.
- Download check: `docker compose exec -T worker python -c "import worker;p=worker.download_video('https://www.youtube.com/watch?v=jNQXAC9IVRw','dlcheck');print(p);p.unlink()"`
  → 2026-10-09: 629 KB in 34 s (incl. the 20 s gap). Bot path tested with a fake failure: permanent + alert sent.
