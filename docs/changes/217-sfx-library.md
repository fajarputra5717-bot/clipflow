# 217 — Sound effects library: uploads + Freesound search, per-user sound per category

Owner request 2026-10-14 (plan confirmed; backend processing chosen over a worker queue).

## What
- **Categories** = the sound names the mixer knows (`edit_director.SFX`): laugh (new), ding, whoosh, boom, bass_hit,
  record_scratch. A user assigns at most one of their own sounds to each (`uq_sfx_assets_category`). Render
  resolution per job owner (worker `owner_sfx_paths()` → `render_steps.mix_sfx(sfx_paths=)` →
  `retention.sfx_mix_cmd(paths=)`): assigned sound → bundled `<name>.wav`; laugh has no bundled recording and falls back
  to ding. Funny/Meme's laugh moments now use `sfx: "laugh"` (users without one hear ding, as before).
- **Upload** (`POST /api/sfx`): ≤ 2 MB; real container sniffed from the bytes (RIFF/WAVE, OggS, ID3/frame sync; the
  extension and browser type are ignored); ffprobe/ffmpeg run with the demuxer forced to that format and
  `-protocol_whitelist file` (no playlists/URLs); one audio stream (mp3/vorbis/opus/PCM; cover art ok, video not),
  0.3–10 s; leading silence trimmed, gain to mean −14 dB with peaks ≤ −3 dB (the bundled set's level), 48 kHz PCM WAV.
  ffmpeg was added to the backend image (396 MB → 1.04 GB; Debian's ffmpeg package and its libraries).
- **Freesound** (`GET /api/sfx/freesound/search`, `…/{id}/preview`, `POST …/{id}`): key = env `FREESOUND_API_KEY`
  (`.env`, `Authorization: Token` header only; never a URL, log line, response or the repo). Filter
  `license:"Creative Commons 0" duration:[0.5 TO 4.0]`, 30 results ranked by `sfx_library.score()` (Bayesian rating:
  5 votes of 3.5 as the prior, + 0.5·log10 downloads), top 8 shown with length, licence, author, rating, downloads.
  CC0 + length + preview host (`https://cdn.freesound.org/previews/…`) are re-checked on every result and again on
  save. Save downloads the HQ mp3 preview, runs the upload pipeline and stores source URL, author, licence, Freesound
  id. Nothing is assigned unless the user clicks "Use for <category>" (plain "Save" leaves it unassigned). Previews
  stream through the backend (the browser never contacts Freesound). Caches 10 min; per-user limits 20 searches /
  80 previews / 20 saves per 10 min. Freesound trouble → 409 (no/refused key) or 424, never 502/503 (the frontend
  reads those as "ClipFlow is updating").
- **Ownership**: `sfx_assets.user_id` NOT NULL; every query filters by the caller; `SFX_PATH_RE` in the middleware guard
  404s `/api/sfx/<id>…` for rows that aren't the caller's (admins included). File + preview routes are in
  `MEDIA_PATH_RE` (`<audio>` src via `mediaUrl()`).
- **UI**: Settings → "Sound effects" row opens `#sfxSheet`: categories (sound in use: "Yours: …" / built-in, which packs
  use it, play, Find sounds panel), My sounds (play, rename inline, "Use for …" select, delete with Undo, Freesound
  link), drop zone / file picker. Built-in sounds are public at `/sfx/<name>.wav` (nginx alias of worker/assets/sfx,
  new frontend mount in both compose files). Escape inside `[data-esc-local]` no longer closes the sheet.
- Changes apply from the next preview/final render (resolved per render, like the watermark); finished renders keep
  their sound.

## Files
shared/sfx_library.py (new), backend/app/routes_sfx.py (new), backend/app/main.py (schema, guard, MEDIA_PATH_RE, router),
backend/Dockerfile, worker/worker.py, worker/render_steps.py, shared/retention.py + shared/style_packs.py +
shared/edit_director.py (Lane B modules, small additive changes, Lane B told), frontend/html/index.html,
frontend/conf.d/default.conf, docker-compose(.staging).yml, worker/assets/LICENSES.md.

## Tests
tests/test_sfx_library.py (rules, ranking, commands), tests/test_sfx_upload.py (real ffmpeg, backend image: formats,
extension spoofing incl. an HLS playlist named .mp3, length, silence trim, levels), tests/test_sfx_routes.py (fake
Freesound: key only in the header, errors, cache, CC0 re-check on save, preview host, rate limit),
tests/ui/specs/sfx.spec.js (12) + touch.spec (the sheet with a Find panel open, phone). End-to-end against a throwaway
backend + Postgres: upload, too long, fake mp3, assign moves the category, rename/unassign, member 404 on another
user's file/PATCH/DELETE, unauthenticated 401.

## Deploy
Backend rebuild (ffmpeg) → healthy (creates `sfx_assets`) → worker + sender → frontend **recreate** (new /sfx mount;
conf.d change). Add `FREESOUND_API_KEY=` to `.env` (owner) and recreate the backend to enable search; uploads work
without it.
