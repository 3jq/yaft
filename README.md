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
- Voice messages, LLM parsing, WebApp dashboard, budgets, goals, recurring, AI analysis, deployment: not yet — see `docs/superpowers/plans/`.
