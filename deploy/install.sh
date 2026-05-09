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

# WebApp build (assumes Node 20+ already installed).
( cd "$APP_DIR/webapp" && \
    sudo -u "$USER_" npm ci && \
    sudo -u "$USER_" npm run build )

# Migrations
sudo -u "$USER_" "$APP_DIR/.venv/bin/alembic" \
  -c "$APP_DIR/alembic.ini" upgrade head

# Service
sudo install -m 0644 \
  "$APP_DIR/deploy/yaft.service" \
  /etc/systemd/system/yaft.service
sudo systemctl daemon-reload
sudo systemctl enable --now yaft

echo "Done. Tail logs with: journalctl -u yaft -f"
