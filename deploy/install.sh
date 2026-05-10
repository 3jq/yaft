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

sudo rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'webapp/node_modules' \
  --exclude '/finance.db' \
  --exclude '/yaft.db' \
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

# Migrations — load the runtime env file (so DB_URL matches what the systemd
# unit will use) and cd into APP_DIR so alembic's relative `script_location`
# resolves correctly. Skip cleanly if the env file isn't there yet (first
# install — the operator hasn't created /etc/yaft.env yet; alembic will run
# automatically on next install after they create it).
ENV_FILE=/etc/yaft.env
if [ -r "$ENV_FILE" ]; then
  ( cd "$APP_DIR" && \
    sudo -E -u "$USER_" \
      env $(sudo grep -E '^[A-Z_]+=' "$ENV_FILE" | xargs -d '\n') \
      "$APP_DIR/.venv/bin/alembic" \
        -c "$APP_DIR/alembic.ini" upgrade head )
else
  echo "NOTE: $ENV_FILE not present yet — skipping alembic. Create the env" >&2
  echo "      file, then re-run: sudo bash deploy/install.sh" >&2
fi

# Service
sudo install -m 0644 \
  "$APP_DIR/deploy/yaft.service" \
  /etc/systemd/system/yaft.service
sudo systemctl daemon-reload
sudo systemctl enable yaft
sudo systemctl restart yaft

echo "Done. Tail logs with: journalctl -u yaft -f"
