# Finance App

Personal AI-powered budgeting via Telegram bot + WebApp dashboard.

## Dev setup
    python -m venv .venv && source .venv/bin/activate
    pip install -e '.[dev]'
    cp .env.example .env  # fill in BOT_TOKEN, OWNER_TG_ID
    alembic upgrade head
    python -m finance_app.app
