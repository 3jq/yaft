#!/usr/bin/env bash
# Install/update the yaft on a Debian/Ubuntu VPS.
# Idempotent — re-run after `git pull` to update.
set -euo pipefail

APP_DIR=/opt/yaft
DATA_DIR=/var/lib/yaft
BACKUP_DIR="$DATA_DIR/backups"
USER_=yaft

id -u "$USER_" >/dev/null 2>&1 || \
  sudo useradd --system --create-home --home-dir "$DATA_DIR" "$USER_"

sudo install -d -o "$USER_" -g "$USER_" "$APP_DIR" "$DATA_DIR" "$BACKUP_DIR"

sudo rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'webapp/node_modules' \
  --exclude '.git' \
  ./ "$APP_DIR"/

sudo chown -R "$USER_:$USER_" "$APP_DIR"

if [ ! -d "$APP_DIR/.venv" ]; then
  sudo -u "$USER_" python3.12 -m venv "$APP_DIR/.venv"
fi
sudo -u "$USER_" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$USER_" "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

# WebApp: prebuilt dist/ is shipped in the repo, so no `npm` step on the VPS.
# (Build locally with `cd webapp && npm install && npm run build` before
# committing — keeps the deploy host RAM-light, important on small VPS sizes.)
if [ ! -d "$APP_DIR/webapp/dist" ]; then
  echo "FATAL: webapp/dist/ missing — build the WebApp locally and commit it." >&2
  exit 1
fi

# Migrations — cd into APP_DIR so alembic's relative `script_location` and
# `prepend_sys_path = .` resolve against the deployed copy, not whatever
# directory the operator happened to be in when running this script.
( cd "$APP_DIR" && \
  sudo -u "$USER_" "$APP_DIR/.venv/bin/alembic" \
    -c "$APP_DIR/alembic.ini" upgrade head )

# Service
sudo install -m 0644 \
  "$APP_DIR/deploy/yaft.service" \
  /etc/systemd/system/yaft.service
sudo systemctl daemon-reload
sudo systemctl enable yaft
sudo systemctl restart yaft

echo "Done. Tail logs with: journalctl -u yaft -f"
