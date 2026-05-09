from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

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

def _category_path(cat_by_id: dict[int, object], cid: int | None) -> str | None:
    if cid is None or cid not in cat_by_id:
        return None
    c = cat_by_id[cid]
    if getattr(c, "parent_id", None) and c.parent_id in cat_by_id:
        return f"{cat_by_id[c.parent_id].name} / {c.name}"
    return c.name


def render_group_card(
    legs: list[Transaction],
    *,
    account_by_id: dict[int, object],
    category_by_id: dict[int, object],
    base_currency: str,
) -> str:
    """Render a card for a multi-leg group (split or transfer). One row per leg."""
    if not legs:
        return ""
    primary = legs[0]
    is_transfer = any(t.kind in ("transfer_out", "transfer_in") for t in legs)
    is_split = (not is_transfer) and len(legs) > 1
    when = primary.occurred_at.strftime("%Y-%m-%d %H:%M")
    if is_transfer:
        head = "✅ Transfer"
        # Sum just the out leg amount (or any single leg — they're equal in original ccy)
        out_leg = next((t for t in legs if t.kind == "transfer_out"), legs[0])
        total = format_amount(out_leg.amount_minor, out_leg.currency)
        base = ""
        if out_leg.currency != base_currency:
            base = f" (≈ {format_amount(out_leg.base_amount_minor, base_currency)})"
        body = f"{head} · {total}{base} · {when}"
        for t in sorted(legs, key=lambda x: x.kind):
            sign = "−" if t.kind == "transfer_out" else "+"
            acc = account_by_id.get(t.account_id)
            acc_name = acc.name if acc else f"#{t.account_id}"
            body += f"\n  {sign} {format_amount(t.amount_minor, t.currency)} · {acc_name}"
        return body
    if is_split:
        total = sum(t.amount_minor for t in legs)
        total_base = sum(t.base_amount_minor for t in legs)
        head = "✅ Recorded (split)"
        currency = primary.currency
        main = f"−{format_amount(total, currency)}"
        base = ""
        if currency != base_currency:
            base = f" (≈ −{format_amount(total_base, base_currency)})"
        acc = account_by_id.get(primary.account_id)
        acc_name = acc.name if acc else f"#{primary.account_id}"
        body = f"{head} · {main}{base} · {acc_name} · {when}"
        for t in legs:
            cat = _category_path(category_by_id, t.category_id) or "(no category)"
            note = f" — {t.note}" if t.note else ""
            body += f"\n  · −{format_amount(t.amount_minor, t.currency)} · {cat}{note}"
        return body
    # Single-leg fallback: defer to render_card
    cat_path = _category_path(category_by_id, primary.category_id)
    acc = account_by_id.get(primary.account_id)
    acc_name = acc.name if acc else f"#{primary.account_id}"
    return render_card(
        primary, account_name=acc_name, category_path=cat_path, base_currency=base_currency,
    )


def build_keyboard(tx_id: int, *, webapp_base: str | None = None) -> InlineKeyboardMarkup:
    edit_btn = (
        InlineKeyboardButton(
            text="✏️ Edit",
            web_app=WebAppInfo(url=f"{webapp_base}/transactions/{tx_id}"),
        )
        if webapp_base else
        InlineKeyboardButton(text="✏️ Edit", callback_data=f"{CB_PREFIX}:edit:{tx_id}")
    )
    split_btn = (
        InlineKeyboardButton(
            text="🔀 Split",
            web_app=WebAppInfo(url=f"{webapp_base}/transactions/{tx_id}"),
        )
        if webapp_base else
        InlineKeyboardButton(text="🔀 Split", callback_data=f"{CB_PREFIX}:split:{tx_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            edit_btn,
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"{CB_PREFIX}:del:{tx_id}"),
        ],
        [
            InlineKeyboardButton(text="🔁 Retry", callback_data=f"{CB_PREFIX}:retry:{tx_id}"),
            split_btn,
        ],
    ])
