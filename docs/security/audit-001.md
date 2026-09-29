# Security audit 001 — threat model + findings (TASKS-4-SECURITY T1)
Date: 2026-09-29 · Code base: lane-b/qa @ 3231a5e (R-03…R-06 landed) · No code changed by this audit

## Scope, standard, method

- **Standard:** OWASP ASVS 4.0 **Level 1** + the relevant OWASP Top 10 (2021) categories. This report does
  not claim ASVS compliance. It covers the ten areas in the task and nothing else.
- **Target:** this instance only. Live probes went to `127.0.0.1:8081` (the lane-B preview nginx, which proxies to the
  same backend as `:80`). No third party was scanned. The OSV vulnerability database was queried with package
  names and versions only.
- **Unauthenticated tests only.** `CLIPFLOW_API_KEY` lives in `.env`, which this lane may not read. Every finding
  that needs the key is **verified by code reading** and marked that way. Nothing was executed against the shared
  worker. No secrets, tokens or request bodies are reproduced here.

## Threat model (this deployment)

| Asset | Why it matters |
|---|---|
| Provider keys (Gemini, Anthropic, Submagic, YouTube/TikTok/Instagram tokens) | Real money and account takeover |
| Submagic `/export` | Each call is billed |
| Unpublished clips on `/data` | Private content |
| Host / LAN | The VM sits on the home LAN (10.10.10.0/24) next to the Proxmox host |

**Exposure (checked with `ss -ltnp`):** only nginx `:80` is bound to `0.0.0.0`. It is reachable from the LAN and
over **Tailscale**. There is **no public exposure**: no port-forward, no public HTTPS. `:8000` (API) and
`:8081` (preview) are bound to `127.0.0.1`, and Postgres is not published. Tailscale is not installed on the VM
itself, so the tailnet reaches it through a subnet router or the host. That is the assumption; confirm it.

**Actors, most to least likely:** (1) the owner's own client misbehaving (a retry loop, a double click);
(2) another device or guest on the LAN, or a compromised IoT box; (3) a tailnet member other than the owner;
(4) someone holding a leaked media URL. Internet attackers can reach the app only through one of those.

## Summary

| # | Finding | Severity here | Status |
|---|---|---|---|
| F1 | No authentication on `/api/*` | was Critical | **Closed** by R-03 |
| F2 | CORS `*` + credentials | was Medium | **Closed** by R-03 |
| F3 | `.env.swp` editor swap file leaked secrets | was Critical | **Closed** (purged, keys rotated) |
| F4 | yt-dlp URL: option injection + SSRF, no validation | **Medium** | **Mitigated** (063: API allowlist); worker `--` still open |
| F5 | Upload fallback stores raw bytes when Pillow fails (bombs, SVG, junk) | **Medium** | **Fixed** (063) |
| F6 | No rate limits or spend caps on paid routes | **Medium** | Open → T4 |
| F7 | API key and media tokens travel over plain HTTP on the LAN | Low | Open (accepted?) |
| F8 | Error bodies leak `str(exc)` and absolute paths | Low | Open → T3 |
| F9 | File-serving routes trust DB paths (absolute paths honoured, no containment check) | Low | Open → T3 |
| F10 | `subtitles=` filter escapes only `'` | Low (latent) | Open → T3 |
| F11 | No security headers (CSP, nosniff, frame-ancestors) | Low | Open |
| F12 | Media tokens are written to nginx access logs | Info | Accepted in R-03 |
| F13 | Settings masking: 9 of 10 secret-ish keys are masked | Info | OK |
| F14 | SQL injection | None found | OK |
| F15 | Dependencies: 1 package with advisories, no runtime path | Info | OK |

## Closed findings

### F1 — Authentication (ASVS V2.1/V4.1, A01/A07) — Closed by R-03
Before R-03 every route was open to anyone who could reach `:80`. The damaging routes were `DELETE /api/jobs/{id}`,
the three sync AI routes (Gemini/Claude spend), `submagic/start` + `submagic/export` (**billable**),
`upload-youtube` (publishes to the channel), `PUT /api/settings` (swap keys, redirect uploads) and
`GET /api/settings`.
**Now:** the `require_api_key` middleware covers every `/api/*` path. Re-tested unauthenticated on `:8081`:
`GET /api/jobs`, `/api/settings`, `/api/media-token`, the unknown path `/api/nonexistent`, `DELETE /api/jobs/x`,
`POST …/submagic/export` and a 50 MB POST to `/api/assets/watermarks` all return **401**. A wrong key returns 401
`{"detail":"Unauthorized"}`. A forged `?mt=` token returns 401. `/health` and `/` return 200. `/docs` and
`/openapi.json` via nginx return the SPA `index.html` (try_files fallback), not FastAPI's docs, so they are not exposed.
**Residual:** a single shared key with full power (no roles). That is acceptable for a one-user tool at L1.

### F2 — CORS (ASVS V14.5.3, A05) — Closed by R-03
Before: `allow_origins=["*"]` with `allow_credentials=True`. Starlette answers that combination by echoing the
origin. There was no cookie to steal, so the real exposure was any web page the owner visited being able to read
and drive the open API from the owner's browser (the page runs on the LAN).
**Now:** a preflight from `Origin: http://evil.example` gets **400 with no `access-control-allow-origin`**. A
simple GET from that origin gets 401 with no ACAO. Credentials are off.

### F3 — Leaked `.env.swp` (ASVS V14.3, A05) — Closed
An editor swap file of `.env` was exposed before the VM loss. It has been purged and **all keys in it were
rotated**. Checked now: `.gitignore` has `.env`, `.env.*` (with `!.env.example`) and `*.swp`. `git log --all` shows
no `*.swp` ever committed, and the only committed env file is `.env.example`. nginx serves only `frontend/html/`,
which contains no dotfiles. Recommendation, not a finding: `location ~ /\. { deny all; }` in nginx as belt-and-braces.

## Open findings

### F4 — yt-dlp: argument injection + SSRF (ASVS V5.1.3/V12.6.1, A03/A10) — Medium · verified by code reading
`POST /api/jobs` accepts `youtube_url: str` with **no validation**. `worker.py` `download_video` passes it as the
last argv element to `yt-dlp` **without a `--` separator**.
- **Argument injection:** a value starting with `-` is parsed as a yt-dlp option. For example
  `--batch-file=/proc/self/environ` makes yt-dlp read a file inside the worker container and treat its content as
  URLs. The failure text goes into `clip_candidates/jobs.error_message` (the worker stores `str(exc)` + the last
  8000 chars of output), and the UI shows it. That is a path to **the worker's environment, including provider
  keys**, which `GET /api/settings` deliberately masks. Other options (`--exec`, `-o`, `--config-location`) widen it.
- **SSRF:** a normal `http://` URL goes to yt-dlp's generic extractor, which fetches any host the worker can reach:
  `127.0.0.1`, the backend on the compose network, the LAN (10.10.10.0/24), and the Proxmox web UI. There is no
  cloud metadata service here, so `169.254.169.254` is moot. The responses are not returned verbatim, but errors are.
- **Impact here:** it requires the API key, so the attacker is the owner or someone who already has the key. It
  still turns "has the key" into "has every provider secret and a LAN pivot". Medium.
- **Fix (T3):** a host allowlist (`youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`), `https` only,
  put `--` before the URL, and stop echoing raw tool output into `error_message`.
- Not executed live: that would run in the shared worker.
- **Status 2026-09-29 (063): mitigated at the API.** `create_job` runs `validate_youtube_url()`: `https` only,
  host ∈ {youtube.com, www., m., music.youtube.com, youtu.be}, no userinfo, port 443 or none, no whitespace or
  control characters, no leading `-`. It returns a 400 with a clear message and stores the stripped URL. Tested with 21
  inputs (6 valid, 15 hostile: `--batch-file=…`, `http://`, `youtube.com.evil.com`, `youtube.com@10.10.10.1`, `:8443`,
  IP literals, embedded newline). **Still open:** `worker.py` must put `--` before the URL in the yt-dlp argv
  (defence in depth, Lane A). Rows created before 063 were not validated; a re-run of such a job skips this check.
  Echoing raw tool output into `error_message` is unchanged.

### F5 — Uploads fall back to raw bytes (ASVS V12.1/V12.2, A04) — Medium · verified by code reading
Thumbnail (`…/thumbnail-upload`) and watermark (`/api/assets/watermarks`) uploads:
- The type check is the **client-supplied** `Content-Type` `image/*` only. No magic-byte check.
- Both re-encode through Pillow, but `except Exception: out_path.write_bytes(raw)`. **Anything Pillow rejects is
  stored verbatim** as `.png`/`.jpg`: SVG with script, HTML, truncated or corrupt files. The same goes for
  **decompression bombs**, because Pillow's `DecompressionBombError` is an `Exception`. So the guard against bombs
  is exactly what routes them to disk. A stored watermark is then decoded by ffmpeg in every render, and the
  thumbnail by the browser. The likely result is a stuck or failed render (DoS of the owner's own queue).
- Served back with a fixed `image/png` / `image/jpeg` type. Modern browsers don't sniff `image/*` into HTML, so
  stored XSS is not practical. There is no `nosniff` (F11).
- **Filename / traversal:** safe. The stored names are server-generated (`uuid4`). The client `filename` is saved
  only as a display string, and the frontend escapes it (`esc()`). Both paths are built under `DATA_ROOT`.
- **Size:** the whole body is read into memory before the 5 / 8 MB check. nginx caps bodies at 64 MB, so this
  bounds memory per request, but it is not a streaming limit.
- **Fix (T3):** reject on Pillow failure (never the raw fallback), magic-byte check, set `Image.MAX_IMAGE_PIXELS`
  explicitly and treat the warning as an error, and stream with a limit.
- **Status 2026-09-29 (063): fixed.** Both handlers call `reencode_uploaded_image()` before any DB or disk write. It
  runs Pillow `open` + `verify`, then a fresh decode. It enforces a 40 MP cap (explicit check, plus
  `Image.MAX_IMAGE_PIXELS` with `DecompressionBombWarning` raised as an error) and re-encodes (thumbnail → JPEG q92,
  watermark → RGBA PNG). Every failure → 400, and the raw bytes are never written. Pillow's decoder acts as the
  magic-byte check. Tested: SVG sent as `image/png`, HTML, truncated PNG, 100 MP bomb (12 KB file), and 45 MP → 400.
  A valid PNG passes. **Still open:** the body is read fully before the size check (bounded by nginx's 64 MB).

### F6 — No rate limiting or spend guards (ASVS V11.1.4, A04) — Medium · verified by code reading
There are no per-route limits, no daily caps and no concurrency cap on job creation. The paid paths are:
`new-hook`, `fix-subtitle-ai`, `generate-description` (sync AI), `generate-thumbnails-ai` (queued AI),
`submagic/start` (upload + transcription), **`submagic/export` (billable per call)**, `upload-youtube` (API quota),
and `POST /api/jobs` (download + Whisper + disk). The realistic threat is actor (1): a client bug or retry loop,
not an attacker. `autoRender:false` means `export` is the only money call, so a daily cap there covers most of the
risk (T4).

### F7 — Plain HTTP on the LAN (ASVS V9.1.1, A02) — Low
`X-ClipFlow-Key` and media tokens cross the LAN in cleartext on `:80`. Over Tailscale the traffic is WireGuard-
encrypted, so the exposure is LAN sniffing only (Wi-Fi guests, a compromised device). Options: serve over the
tailnet only (`tailscale serve` gives HTTPS with a tailnet cert) and bind `:80` to the Tailscale IP, or accept it
and document. This is a decision for the owner.

### F8 — Error detail leakage (ASVS V7.4.1, A05) — Low
There are 34 `HTTPException(500, detail=str(exc))` sites in main.py (DB errors, internals). The file routes return
`"File missing on disk: {absolute path}"`, which reveals the `/data` layout. All of these are behind the key. Fix:
a generic 500 body, with the detail kept in the log.

### F9 — File serving trusts DB paths (ASVS V12.3.1, A01) — Low · verified by code reading
The candidate file route (`preview`/`render`/`thumbnail`), `thumbnail-options/{index}` and the watermark file route
read a path from the DB. They **honour absolute paths** (`if not path.is_absolute(): path = DATA_ROOT / path`) and
never check containment. Today no request field writes a path: PATCH picks from `thumbnail_options` by index,
uploads store server-built paths, and version restore copies DB-derived values. So there is no reachable
traversal. A URL-level attempt (`…/watermarks/..%2f..%2fetc%2fpasswd/file`) returns 401 without a key, and the
id is only a DB lookup key with one. This is defence in depth: `resolve()` + `is_relative_to(DATA_ROOT)` on read (T3).

### F10 — `subtitles=` filter escaping (ASVS V5.3.8, A03) — Low, latent
`render_vertical` builds `subtitles='<path>'` by concatenation and escapes only `'`. The ffmpeg filtergraph also
treats `\ : , ; [ ]` as special. The path is **worker-generated** (`DATA_ROOT/…/<candidate-uuid>_preview.ass`),
so no user input reaches it today. `run_command()` always uses argv-list `subprocess.run` (no `shell=True` anywhere
in main.py, worker.py or shared/), so even a broken filter string can't reach a shell. It would only break or
redirect the filter graph. Fix when touched: full filtergraph escaping, or pass a relative path with `cwd`.

### F11 — Missing security headers (ASVS V14.4, A05) — Low
The only header nginx adds is `Cache-Control`. There is no `Content-Security-Policy`, `X-Content-Type-Options:
nosniff`, `frame-ancestors`/`X-Frame-Options` or `Referrer-Policy`. `Referrer-Policy: no-referrer` also matters
for F12. `Server: nginx/1.27.5` discloses the version.

### F12 — Media tokens in logs (ASVS V7.1.1) — Info
`?mt=` tokens (read-only, 5 GET routes, valid 12–24 h) appear in nginx access logs and browser history. This was
accepted in R-03 (002). Keep the key itself out of URLs, which it currently is.

### F13 — Settings masking (ASVS V14.3.2) — Info
`GET /api/settings` masks every key in `SECRET_SETTING_KEYS` (9: Gemini, Anthropic, Runway, YouTube secret +
refresh token, TikTok secret + token, Instagram token, Submagic) as `••••••••`, whether the value comes from the DB
or env. `PUT` skips the mask string, so it never overwrites a real key with dots. The one secret-looking key that is
not masked is `TIKTOK_CLIENT_KEY`, which is TikTok's public OAuth client id: fine. `CLIPFLOW_API_KEY`,
`CORS_ALLOWED_ORIGINS` and `DATABASE_URL` are env-only and are not served. The last 5000 log lines of backend and
worker contain **0** matches for Gemini / Anthropic key patterns or the API-key header. The worker logs full argv
(`RUN: …`), but no call site passes a key on the command line. The real leak path is F4.

### F14 — SQL injection (ASVS V5.3.4, A03) — none found
The candidate PATCH (`update_candidate` in main.py) builds `fields` from **hard-coded column names** chosen by
which Pydantic fields are set. Every value is a `%s` parameter. `worker.py` `update_candidate(**kwargs)` interpolates
kwarg names as columns, but every caller passes literals. Keep it off request dicts. No f-string SQL takes request data.

### F15 — Dependencies (ASVS V14.2.1, A06) — Info
`pip freeze` from both images was checked against OSV (pip-audit can't be installed on the host: no pip):
- backend: 45 packages, **0** advisories.
- worker: 70 packages. `setuptools 78.1.0` has 4 advisories (GHSA-5rjg-fvgr-3xxf, GHSA-h35f-9h28-mq5c,
  PYSEC-2025-49, PYSEC-2026-3447). They are in packaging/`PackageIndex` download code, which the app never calls at
  runtime. That is noise, cleared by bumping setuptools on the next image build.
- **Not audited:** Debian packages in the images (ffmpeg, libav*, fonts), the nginx image and the Postgres image.

## Not tested / limits
- Nothing authenticated was run live (no key; `.env` is off-limits to this lane). F4, F5, F6, F9 and F10 come from
  code reading.
- No live SSRF or yt-dlp option test (it would run in the shared worker). No actual bomb upload.
- The frontend got a quick XSS pass only: 23 `innerHTML` sites, and dynamic text goes through `esc()`. There was no
  full DOM-XSS review. The API key sits in `sessionStorage`, so any future XSS would expose it.
- Tailscale ACLs and the Proxmox firewall were not inspected from this VM.
