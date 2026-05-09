# Finance App

Personal AI-powered budgeting via Telegram bot + WebApp dashboard.

## Dev setup
    python -m venv .venv && source .venv/bin/activate
    pip install -e '.[dev]'
    cp .env.example .env  # fill in BOT_TOKEN, OWNER_TG_ID
    alembic upgrade head
    python -m finance_app.app

## Phase 1 status
- Text capture works end-to-end (Russian + English notes pass through unchanged).
- Multi-currency with snapshotted FX via `open.er-api.com` (free, no API key).
- Edit-card buttons: Delete works; Edit / Retry / Split are placeholders for later phases.

## Phase 2 status
- Voice + LLM parsing live. Russian + English handled by Gemini 2.5 Flash (STT) and GPT-4.1-mini (parse).
- Free-form text (e.g. "had lunch yesterday for $15") routes through the LLM via a regex fast-path.
- Splits and transfers from voice/text work end-to-end (record-level — Edit/Split UI come in Phase 3).
- 🔁 Retry re-parses with a "previous parse was wrong" hint and group-wide soft-deletes the old transaction.
- WebApp dashboard, budgets, goals, recurring, AI analysis, deployment: not yet — see `docs/superpowers/plans/`.

OpenRouter is accessed via the OpenAI Python SDK pointed at `https://openrouter.ai/api/v1` — set `OPENROUTER_API_KEY` in `.env`. The bot still works without it for `/start`, `/help`, `/balance`, `/list`, and regex-fast-path text records; a startup warning logs when the key is missing.

## Phase 3 status
- WebApp dashboard live: Home, Transactions, TransactionEdit, Budgets/Goals/Ask (stubs), Accounts, Categories, Settings.
- Locked monochrome design language: Geist Sans/Mono, hairline section dividers, hand-rolled SVG donut/heatmap/sparkbar/ring. Source-of-truth mockups in `docs/design/`.
- Bot ✏️&nbsp;Edit and 🔀&nbsp;Split buttons now open the WebApp (when `PUBLIC_HTTPS_URL` is set); persistent bot menu button opens `/app/`.
- All `/api/*` routes authenticate via Telegram `initData` HMAC + owner allowlist.
- Build: `cd webapp && npm install && npm run build` produces `webapp/dist/`, served by FastAPI at `/app/`.

To expose the WebApp publicly without buying a domain: `sudo tailscale funnel --bg 8080`, then put the printed `https://<host>.ts.net` into `.env` as `PUBLIC_HTTPS_URL`. Restart the bot. Open it from Telegram via the bot's "Dashboard" menu button.
