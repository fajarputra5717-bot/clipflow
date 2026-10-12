# lane-b 247db67 staging mounts shared/ui · Lane C · 2026-10-12
One line in docker-compose.staging.yml (same /usr/share/nginx/ui mount as production). Staging only, no app code; fixes the SPA-fallback for /ui/tokens.css on :8080. No findings. Prod riftstorm-* all running, restarts=0. Main: nothing new since 6080b3f; no phase gate reported.
Merge: OK (no effect on production).
