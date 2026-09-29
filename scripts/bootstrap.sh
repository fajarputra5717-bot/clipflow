#!/usr/bin/env bash
# ClipFlow bootstrap: run ONCE on the new Ubuntu VM, as root, from the
# unpacked kit folder:   sudo bash scripts/bootstrap.sh
#
# Installs the kit to /opt/riftstorm, generates secrets into .env,
# prepares /data, makes the first git commit, builds and starts the stack.
# Safe to re-run: it never overwrites an existing .env or database.
set -euo pipefail

APP_DIR=/opt/riftstorm
APP_USER=${APP_USER:-clipflow}          # the Linux user Claude Code runs as
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo"; exit 1; }
command -v docker >/dev/null || { echo "Docker missing: do runbook Phase 4b first"; exit 1; }
mountpoint -q /data || echo "WARNING: /data is not a separate mount (runbook Phase 4a). Continuing on the system disk."

# 1) Copy files (never clobber an existing .env)
mkdir -p "$APP_DIR"
if [ "$KIT_DIR" != "$APP_DIR" ]; then
  rsync -a --exclude .env "$KIT_DIR"/ "$APP_DIR"/
fi
cd "$APP_DIR"

# 2) .env with generated secrets
if [ ! -f .env ]; then
  VM_IP=$(hostname -I | awk '{print $1}')
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
      -e "s|^CLIPFLOW_API_KEY=.*|CLIPFLOW_API_KEY=$(openssl rand -hex 32)|" \
      -e "s|__VM_IP__|${VM_IP}|" \
      .env.example > .env
  chmod 600 .env
  echo ">> Created .env (secrets generated). Add GEMINI_API_KEY etc. now or later: nano $APP_DIR/.env"
else
  echo ">> Keeping existing .env"
fi

# 3) Data folders
mkdir -p /data/{downloads,normalized,audio,subtitles,previews,final,thumbnails,watermarks,backups}

# 4) Ownership so Claude Code (running as $APP_USER) can edit and run compose
if id "$APP_USER" >/dev/null 2>&1; then
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
  usermod -aG docker "$APP_USER"
fi

# 5) git: first commit (baseline). .env is gitignored.
if [ ! -d .git ]; then
  sudo -u "${APP_USER}" git -C "$APP_DIR" init -b main -q 2>/dev/null || git init -b main -q
  sudo -u "${APP_USER}" git -C "$APP_DIR" add -A
  sudo -u "${APP_USER}" git -C "$APP_DIR" -c user.name="ClipFlow" -c user.email="clipflow@localhost" \
      commit -q -m "chore: rebuild baseline v2.1100 after VM loss"
  git -C "$APP_DIR" ls-files | grep -qx ".env" && { echo "!! .env got committed, aborting"; exit 1; }
fi

# 6) Build + start
docker compose build
docker compose up -d
echo ">> Waiting for backend..."
for i in $(seq 1 60); do
  curl -fsS http://127.0.0.1/health >/dev/null 2>&1 && break
  sleep 3
done
docker compose ps
curl -fsS http://127.0.0.1/health && echo && echo ">> ClipFlow is up: http://$(hostname -I | awk '{print $1}')/"
