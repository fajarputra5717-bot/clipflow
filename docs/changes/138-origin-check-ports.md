# 138 · Origin check compares scheme + host + port (non-80 deployments work); nginx forwards X-Forwarded-Host · shared/origins.py, main.py, nginx

- **Bug (found by Lane B on staging :8080):** `_origin_allowed()` compared the Origin's host:port with the `Host`
  header, which nginx forwarded without the port, so every cookie-authenticated write from a UI on a non-80 port got
  403 "Cross-origin request refused" (prod on :80 happened to match). Lane B patched staging with a CORS list (3937439).
- **Fix:** `shared/origins.allowed(origin, scheme, host, forwarded_port, extra)` compares (scheme, host, port) with
  default ports normalised (http 80, https 443); "null"/non-http origins refused. The backend uses X-Forwarded-Proto
  + X-Forwarded-Host (+ X-Forwarded-Port from other proxies), else the request's own. nginx now sends
  `X-Forwarded-Host $http_host` (the Host exactly as the browser sent it; `$server_port` is the container's 80).
  Other origins (e.g. a Tailscale name) go in the existing env list `CORS_ALLOWED_ORIGINS`.

**Verified:** `tests.test_origins` OK (80 vs implicit, :8080 via $http_host and via X-Forwarded-Port, the old bug's
input refused, scheme/host/suffix mismatches, IPv6, configured list); prod (session, wrong current password so
nothing changes): Origin http://localhost and :80 → 400 (reached the handler), :8080 / https / evil → 403, no Origin
→ 400. Harness passed. Lane B can drop 3937439 after merging main.

**Staging (lane-b 44ff213 = main f66cb90, no staging Origin patch, CORS list without :8080), user lane-a-origin via
nginx :8080:** Origin http://localhost:8080 → reaches the handler (400 wrong current password); http://localhost,
:80, https://…:8080, evil:8080 → 403; a real settings write from :8080 → 200.
