#!/usr/bin/env bash
# Staging stack (docs/staging.md). Usage: scripts/staging.sh up|down|reset|status|logs [svc]|rebuild [svc]|psql
# Never touches riftstorm-* containers or riftstorm_postgres_data.
set -euo pipefail
cd "$(dirname "$0")/.."
PROD_ENV=/opt/clipflow/.env
DC=(docker compose -p clipflow-staging -f docker-compose.staging.yml --env-file .env.staging)

make_env() {   # staging env = production env minus every outbound/billable integration (never printed)
  local keep_pw=""
  [ -f .env.staging ] && keep_pw=$(grep -m1 '^STAGING_ADMIN_PASSWORD=' .env.staging | cut -d= -f2- || true)
  grep -vE '^(TELEGRAM_|SUBMAGIC_API_KEY|YOUTUBE_|RUNWAY_API_KEY|CLIPFLOW_ADMIN_PASSWORD|STAGING_ADMIN_)' "$PROD_ENV" > .env.staging
  # P1.5: staging admins get their OWN password (production's is never copied); kept across resets
  [ -n "$keep_pw" ] || keep_pw=$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)
  printf 'STAGING_ADMIN_PASSWORD=%s\n' "$keep_pw" >> .env.staging
  staging_origins
}
staging_origins() {  # writes from the :8080 UI: main's origin check compares Origin with Host, and nginx
  # forwards Host without the port, so staging must list its own origins (production's + :8080, localhost)
  local prod o out="http://localhost:8080"
  prod=$(grep -m1 '^CORS_ALLOWED_ORIGINS=' "$PROD_ENV" | cut -d= -f2- | tr -d '"'"'" || true)
  for o in ${prod//,/ }; do
    o=${o%/}
    if [[ "$o" =~ ^(https?://[^:/]+):[0-9]+$ ]]; then out="$out,${BASH_REMATCH[1]}:8080"; else out="$out,$o:8080"; fi
  done
  sed -i '/^CORS_ALLOWED_ORIGINS=/d' .env.staging
  printf 'CORS_ALLOWED_ORIGINS=%s\n' "$(echo "$out" | tr ',' '\n' | awk '!seen[$0]++' | paste -sd,)" >> .env.staging
  printf 'TELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\nSUBMAGIC_API_KEY=\nYOUTUBE_CLIENT_ID=\nYOUTUBE_CLIENT_SECRET=\nYOUTUBE_REFRESH_TOKEN=\nRUNWAY_API_KEY=\n' >> .env.staging
  chmod 600 .env.staging
}
pg() { "${DC[@]}" exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }

reset() {
  local dump; dump=$(ls -1 /data/backups/clipflow-*.sql.gz | sort | tail -1)
  echo "reset: restoring $(basename "$dump") into a fresh staging DB"
  "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true   # staging volumes only (hf_cache is external)
  mkdir -p /data-staging && rm -rf /data-staging/* && mkdir -p /data-staging/{downloads,audio,subtitles,previews,final,normalized,thumbnails,watermarks}
  cp -a /data/watermarks/. /data-staging/watermarks/        # relative DB paths (watermark_assets.path)
  cp -a /data/thumbnails/. /data-staging/thumbnails/ 2>/dev/null || true
  "${DC[@]}" up -d --wait postgres
  zcat "$dump" | pg
  # park everything that was in flight in production, so the staging worker doesn't reprocess it
  pg <<'SQL'
UPDATE jobs SET status='cancelled', message='parked by staging reset'
 WHERE status NOT IN ('completed','failed','cancelled','review','partial_failure');
UPDATE clip_candidates SET status='failed', message='parked by staging reset'
 WHERE status IN ('queued','preview_queued','preview_rendering','render_queued','rendering','thumbnail_queued','thumbnail_rendering');
UPDATE clip_candidates SET submagic_status='failed'
 WHERE submagic_status IS NOT NULL AND submagic_status NOT IN ('failed','applied','completed','transcribed');
DELETE FROM app_settings WHERE key IN ('ORPHAN_SWEEP_DRY_RUN','RETENTION_DAYS_INTERMEDIATE');
SQL
  up
  staging_admin
}
staging_admin() {   # every admin account on staging → STAGING_ADMIN_PASSWORD; their sessions dropped
  "${DC[@]}" exec -T backend python - <<'PY2'
import os, psycopg
from app import auth
pw = os.environ["STAGING_ADMIN_PASSWORD"]
with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
    cur.execute("UPDATE users SET password_hash = %s WHERE role = 'admin' RETURNING username", (auth.hash_password(pw),))
    names = [r[0] for r in cur.fetchall()]
    cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE role = 'admin')")
    conn.commit()
print("staging admin login set for:", ", ".join(names) or "(no admin user)")
PY2
}
purge_auth() {   # restored from production: no session or API token from there may work on staging
  "${DC[@]}" exec -T postgres sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM user_sessions; DELETE FROM api_tokens; DELETE FROM login_failures;"' >/dev/null 2>&1 \
    && echo "staging: sessions + API tokens cleared" || echo "staging: (no auth tables yet)"
}
up() { "${DC[@]}" up -d --build 2>&1 | tail -3; purge_auth; status; }
status() { "${DC[@]}" ps --format '{{.Service}}\t{{.Status}}'; echo "UI http://localhost:8080  API http://127.0.0.1:8001/health"; }

[ -f .env.staging ] || make_env
case "${1:-status}" in
  up) up ;;
  down) "${DC[@]}" down ;;                       # keeps the staging DB volume
  reset) make_env; reset ;;
  status) status ;;
  logs) "${DC[@]}" logs --tail=80 "${2:-worker}" ;;
  rebuild) "${DC[@]}" up -d --build "${2:-worker}" 2>&1 | tail -3 ;;
  admin) staging_admin ;;
  origins) staging_origins; "${DC[@]}" up -d backend 2>&1 | tail -1 ;;
  psql) "${DC[@]}" exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' ;;
  *) echo "usage: $0 up|down|reset|status|logs [svc]|rebuild [svc]|admin|origins|psql"; exit 2 ;;
esac
