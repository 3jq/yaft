# Operations

## Prereqs
- Debian/Ubuntu VPS, Python 3.12, Node 20+, sqlite3, rclone (optional).
- A Cloudflare-managed domain for the tunnel hostname (Cloudflare Tunnel is
  the chosen path here; Tailscale Funnel works as a fallback if you don't
  want a domain).

## /etc/finance-app.env
Owned by root, mode 0640, group `finance`. Required keys:

```
BOT_TOKEN=...
OWNER_TG_ID=...
OPENROUTER_API_KEY=...
BASE_CURRENCY=USD
TIMEZONE=Europe/Berlin
DB_URL=sqlite+aiosqlite:////var/lib/finance/finance.db
BACKUP_DIR=/var/lib/finance/backups
BACKUP_RCLONE_REMOTE=gdrive:finance-backups
PUBLIC_HTTPS_URL=https://<your-funnel-host>
LOG_LEVEL=INFO
```

After editing: `sudo systemctl restart finance-app`.

## First-time deploy

```bash
git clone <repo> finance-app && cd finance-app
sudo bash deploy/install.sh
sudoedit /etc/finance-app.env       # paste env values
sudo systemctl restart finance-app
journalctl -u finance-app -f
```

## Update

```bash
cd finance-app
git pull
sudo bash deploy/install.sh        # idempotent
```

## Cloudflare Tunnel (preferred)

Pick a hostname like `finance.<yourdomain>` (must be a zone you manage in
Cloudflare).

```bash
# Install cloudflared (Debian/Ubuntu)
curl -L https://pkg.cloudflare.com/install.sh | sudo bash
sudo apt install -y cloudflared

# Authenticate (opens a browser auth URL — copy it from the SSH session)
cloudflared tunnel login

# Create the tunnel
cloudflared tunnel create finance-app
# Note the printed tunnel UUID and credentials path
# (~/.cloudflared/<UUID>.json).

# Route the hostname to the tunnel (creates the Cloudflare DNS CNAME for you)
cloudflared tunnel route dns finance-app finance.<yourdomain>

# Config file: /etc/cloudflared/config.yml
sudo tee /etc/cloudflared/config.yml <<'YAML'
tunnel: finance-app
credentials-file: /root/.cloudflared/<UUID>.json
ingress:
  - hostname: finance.<yourdomain>
    service: http://localhost:8080
  - service: http_status:404
YAML

# Run as a systemd service
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Set `PUBLIC_HTTPS_URL=https://finance.<yourdomain>` in
`/etc/finance-app.env` and `sudo systemctl restart finance-app`.

Verify:
```bash
curl -s https://finance.<yourdomain>/healthz
```

## Tailscale Funnel (fallback, no domain required)

```bash
sudo tailscale up
sudo tailscale funnel --bg 8080
tailscale funnel status
```

Set `PUBLIC_HTTPS_URL` to the printed `https://<host>.ts.net` and restart the
unit.

## rclone setup (optional cloud backup)

```bash
rclone config
rclone mkdir gdrive:finance-backups
```

Then set `BACKUP_RCLONE_REMOTE=gdrive:finance-backups` in
`/etc/finance-app.env`. Nightly backups will land both locally and in the
cloud.

## Restore from backup

```bash
gzip -d -c /var/lib/finance/backups/finance-2026-05-09.sqlite.gz \
  > /var/lib/finance/finance.restored.db
sqlite3 /var/lib/finance/finance.restored.db "PRAGMA integrity_check;"
sudo systemctl stop finance-app
mv /var/lib/finance/finance.db /var/lib/finance/finance.db.bak
mv /var/lib/finance/finance.restored.db /var/lib/finance/finance.db
sudo systemctl start finance-app
```

## Logs

```bash
journalctl -u finance-app -f
```

## Healthz

```bash
curl -s http://127.0.0.1:8080/healthz
# {"ok":true}
```

## Heartbeat
The bot DMs you once a day at 12:00 local time:
`❤️ Alive · N tx · M accounts · last backup: …`. If you don't see it
within ~25h, something is wrong — check `journalctl -u finance-app`.
