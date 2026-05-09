# yaft

A personal AI-powered budgeting app I use day-to-day. Talk to a Telegram bot
("12.50 lunch #food @cash" or a 5-second voice note in any language), and an
LLM parses, normalizes, and stores it. A React WebApp opened from inside
Telegram shows balances, budgets, goals, charts, and an LLM advisor that
queries your data and suggests what to actually change.

> Single-user by design. The bot only responds to one Telegram ID; the
> WebApp authenticates via Telegram `initData` HMAC against that same ID.

---

## Features

- **Capture anywhere** — Telegram text or voice, English or Russian. Free-form
  notes ("had lunch yesterday for $15") go through GPT-4.1-mini for parsing;
  voice goes through Gemini 2.5 Flash for transcription. Strict-format
  shortcuts (`+3000 USD salary #salary`) skip the LLM.
- **Multi-currency** — every transaction stores both native and
  base-currency amounts. FX rates snapshotted daily from `open.er-api.com`.
- **WebApp dashboard** — monochrome Geist-typography UI with hand-rolled SVG
  donut/heatmap/sparkbar/goal-ring; opens from a Telegram menu button.
- **Budgets, goals, recurring** — period-bound budgets with deduped alerts at
  50/80/100 % thresholds, savings goals with progress rings, recurring
  rules materialized by APScheduler.
- **AI advisor** — `/ask` runs a tool-using LLM loop against a read-only
  SQLite copy (`PRAGMA query_only=1` + regex allowlist). It pulls a snapshot,
  forms an opinion, and gives concrete advice ("cut takeaway from $X to $Y").
- **Forecast** — deterministic 90-day-trailing extrapolation: end-of-month
  net, runway, days-to-each-goal. LLM only narrates the numbers.
- **Scheduled jobs** — hourly budget alerts, daily recurring materializer,
  daily FX prefetch, weekly savings coach (Sun 09:00), monthly summary
  (1st 09:00), nightly SQLite backup (03:00), daily heartbeat DM (12:00).

## Architecture

```
┌────────────────────┐    text/voice     ┌─────────────────────┐
│  Telegram client   │ ────────────────▶ │  aiogram bot (poll) │
└────────────────────┘ ◀──────────────── └──────────┬──────────┘
       │  WebApp button (Telegram WebApps)          │
       ▼                                            ▼
┌────────────────────┐   /api/*  HMAC   ┌─────────────────────┐
│  React WebApp      │ ────────────────▶│   FastAPI routes    │
│  (Vite, Geist UI)  │ ◀──────────────── │   + APScheduler     │
└────────────────────┘                  └──────────┬──────────┘
                                                   │
                                          SQLite (WAL) on disk
                                                   │
                                          OpenRouter (LLM tools)
```

Both the bot and the API live in a single Python process so APScheduler can
share state with the bot for DMs (alerts, heartbeat, weekly coach,
monthly summary). The WebApp is a static SPA built into `webapp/dist/` and
either served by FastAPI at `/app/` or hosted separately.

## Tech stack

- **Backend** — Python 3.12, FastAPI, aiogram 3, SQLAlchemy 2 (async),
  aiosqlite, Alembic, APScheduler, structlog, Pydantic v2.
- **LLM** — OpenAI Python SDK pointed at OpenRouter
  (`base_url=https://openrouter.ai/api/v1`); GPT-4.1-mini for parsing/advisor,
  Gemini 2.5 Flash for STT.
- **Frontend** — Vite + React 18 + TypeScript, TanStack Query, Tailwind,
  Geist Sans/Mono. Hand-rolled SVG charts (no chart library).
- **Storage** — SQLite (WAL mode, `synchronous=NORMAL`).
- **Deploy** — systemd unit on a small VPS, Cloudflare Tunnel for HTTPS.

## Repo layout

```
src/yaft/
  app.py                 FastAPI + bot bootstrap, lifespan, scheduler wiring
  config.py              Pydantic settings (env-driven)
  bot/                   aiogram handlers, parser, owner allowlist
  api/                   FastAPI routes, Telegram-initData auth
  db/                    SQLAlchemy models, session, migrations
  domain/                budgets, goals, recurring rules, FX, money
  pipeline/              OpenRouter client (parse + tool-using ask loop)
  analysis/              forecast, monthly/weekly aggregates, read-only SQL
  scheduler/             APScheduler jobs (alerts, FX, coach, backup, …)

webapp/                  Vite + React SPA
deploy/                  systemd unit + install script
docs/operations.md       Production runbook
tests/                   Unit + integration tests (~100, 100 % passing)
```

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env       # fill in BOT_TOKEN, OWNER_TG_ID, OPENROUTER_API_KEY
alembic upgrade head
python -m yaft.app  # starts FastAPI on :8080 + bot polling
```

WebApp:

```bash
cd webapp && npm install && npm run build      # → webapp/dist/, served at /app/
# or for hot reload:
cd webapp && npm run dev                        # Vite dev server on :5173
```

Tests:

```bash
pytest                     # ~100 unit + integration tests
ruff check src/ tests/
```

## Production deploy

See [`docs/operations.md`](docs/operations.md) for the full runbook.
TL;DR on a Debian/Ubuntu VPS:

```bash
git clone <repo> ~/yaft && cd ~/yaft
sudo bash deploy/install.sh                # creates user, venv, systemd unit
sudoedit /etc/yaft.env              # paste secrets
# Cloudflare Tunnel (or Tailscale Funnel as fallback)
cloudflared tunnel create yaft
cloudflared tunnel route dns yaft finance.<yourdomain>
sudo systemctl enable --now cloudflared yaft
```

## Configuration

All config is environment-driven (loaded from `.env` locally or
`/etc/yaft.env` in production):

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | yes | Telegram bot token from @BotFather. |
| `OWNER_TG_ID` | yes | Your numeric Telegram user ID. The bot ignores everyone else. |
| `OPENROUTER_API_KEY` | for AI features | OpenRouter API key. Without it, only regex-fast-path text records work. |
| `BASE_CURRENCY` | no | Default `USD`. Used for net-worth aggregation. |
| `TIMEZONE` | no | IANA timezone. Default `UTC`. |
| `DB_URL` | no | SQLAlchemy URL. Default `sqlite+aiosqlite:///./yaft.db`. |
| `PUBLIC_HTTPS_URL` | for WebApp | Public HTTPS URL the bot points the menu button at. |
| `BACKUP_DIR` | no | Backup destination. Default `/var/lib/yaft/backups`. |
| `BACKUP_RCLONE_REMOTE` | no | rclone remote to copy backups to (e.g. `gdrive:yaft-backups`). |
| `LOG_LEVEL` | no | `DEBUG`/`INFO`/`WARNING`. Default `INFO`. |

## License

MIT — see [LICENSE](LICENSE).
