from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from finance_app.db.models import Transaction
from finance_app.domain.money import format_amount

CB_PREFIX = "tx"


def render_card(
    tx: Transaction,
    *,
    account_name: str,
    category_path: str | None,
    base_currency: str,
) -> str:
    sign = "−" if tx.kind in ("expense", "transfer_out") else "+"
    main = f"{sign}{format_amount(tx.amount_minor, tx.currency)}"
    base = ""
    if tx.currency != base_currency:
        base = f" (≈ {sign}{format_amount(tx.base_amount_minor, base_currency)})"
    cat_line = category_path if category_path else "(no category)"
    when = tx.occurred_at.strftime("%Y-%m-%d %H:%M")
    warn = "⚠️ low confidence — please review\n" if (tx.confidence or 1.0) < 0.5 else ""
    note = f"\nnote: {tx.note}" if tx.note else ""
    merchant = f" · {tx.merchant}" if tx.merchant else ""
    head = "✅ Recorded"
    return (f"{head} · {main}{base}\n"
            f"{cat_line}{merchant} · {account_name} · {when}"
            f"{note}\n{warn}")

def build_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Edit",   callback_data=f"{CB_PREFIX}:edit:{tx_id}"),
            InlineKeyboardButton(text="🗑 Delete",  callback_data=f"{CB_PREFIX}:del:{tx_id}"),
        ],
        [
            InlineKeyboardButton(text="🔁 Retry",  callback_data=f"{CB_PREFIX}:retry:{tx_id}"),
            InlineKeyboardButton(text="🔀 Split",  callback_data=f"{CB_PREFIX}:split:{tx_id}"),
        ],
    ])
