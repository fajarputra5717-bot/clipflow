#!/usr/bin/env bash
# Nightly DB dump to /data/backups, keeps 14 days.
# Install: echo "30 2 * * * root /opt/riftstorm/scripts/backup-db.sh" | sudo tee /etc/cron.d/clipflow-backup
set -euo pipefail
cd /opt/riftstorm
set -a; . ./.env; set +a
OUT=/data/backups/clipflow-$(date +%F).sql.gz
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
find /data/backups -name 'clipflow-*.sql.gz' -mtime +14 -delete
