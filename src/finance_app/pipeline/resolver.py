from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_app.bot.parser_text import ParsedTransaction
from finance_app.db.models import Account, Category, Setting
from finance_app.domain.fx import FxService
from finance_app.domain.money import convert, to_minor


@dataclass
class ResolvedTransaction:
    occurred_at: datetime
    account_id: int
    category_id: int | None
    kind: str
    amount_minor: int
    currency: str
    base_amount_minor: int
    fx_rate: float | None
    base_currency: str
    merchant: str | None = None
    note: str | None = None
    confidence: float = 1.0
    ambiguities: list[str] = field(default_factory=list)
    splits: list[dict] | None = None
    transfer_to_account_id: int | None = None


class Resolver:
    def __init__(self, session: AsyncSession, fx: FxService):
        self.s = session
        self.fx = fx

    async def _setting(self, key: str) -> str | None:
        row = (
            await self.s.execute(select(Setting).where(Setting.key == key))
        ).scalar_one_or_none()
        return row.value if row else None

    async def _resolve_account(
        self, name: str | None
    ) -> tuple[int, list[str], float]:
        ambiguities: list[str] = []
        confidence = 1.0
        accounts = (
            await self.s.execute(select(Account).where(Account.archived == 0))
        ).scalars().all()
        if name:
            names = {a.name.lower(): a for a in accounts}
            if name.lower() in names:
                return names[name.lower()].id, ambiguities, confidence
            close = difflib.get_close_matches(name.lower(), names.keys(), n=1, cutoff=0.6)
            if close:
                return names[close[0]].id, ambiguities, confidence
            ambiguities.append(f"account '{name}' not found, used default account")
            confidence = 0.6
        else:
            ambiguities.append("no account specified, used default account")
            confidence = 0.8
        default_id = int(await self._setting("default_account_id") or "1")
        return default_id, ambiguities, confidence

    async def _resolve_category(
        self, path: str | None, kind: str
    ) -> tuple[int | None, list[str], float]:
        if not path:
            return None, [], 1.0
        parts = [p.strip() for p in path.split("/") if p.strip()]
        cats = (
            await self.s.execute(select(Category).where(Category.archived == 0))
        ).scalars().all()
        by_parent: dict[int | None, dict[str, Category]] = {}
        for c in cats:
            by_parent.setdefault(c.parent_id, {})[c.name.lower()] = c

        if len(parts) == 1:
            name = parts[0].lower()
            for _parent_id, m in by_parent.items():
                if name in m:
                    return m[name].id, [], 1.0
            close = difflib.get_close_matches(
                name, [c.name.lower() for c in cats], n=1, cutoff=0.7
            )
            if close:
                return next(c.id for c in cats if c.name.lower() == close[0]), [], 0.9
            new = Category(name=parts[0].title(), kind=kind, parent_id=None)
            self.s.add(new)
            await self.s.flush()
            return new.id, [f"created new category '{new.name}'"], 0.7

        parent = by_parent.get(None, {}).get(parts[0].lower())
        if not parent:
            new_parent = Category(name=parts[0].title(), kind=kind, parent_id=None)
            self.s.add(new_parent)
            await self.s.flush()
            parent = new_parent
        children = by_parent.get(parent.id, {})
        if parts[1].lower() in children:
            return children[parts[1].lower()].id, [], 1.0
        new_child = Category(name=parts[1].title(), kind=kind, parent_id=parent.id)
        self.s.add(new_child)
        await self.s.flush()
        return new_child.id, [f"created new category '{parent.name}/{new_child.name}'"], 0.7

    async def resolve(self, p: ParsedTransaction) -> ResolvedTransaction:
        base_currency = (await self._setting("base_currency")) or "USD"
        ambiguities: list[str] = list(p.ambiguities)
        confidence = p.confidence

        account_id, a_amb, a_conf = await self._resolve_account(p.account)
        ambiguities += a_amb
        confidence *= a_conf

        acct = await self.s.get(Account, account_id)
        if acct is None:
            raise ValueError(
                f"default account id={account_id} not found; check the seed migration ran"
            )
        currency = (p.currency or acct.currency).upper()

        cat_kind = p.kind if p.kind != "transfer" else "transfer"
        cat_id, c_amb, c_conf = await self._resolve_category(p.category, cat_kind)
        ambiguities += c_amb
        confidence *= c_conf

        amount_minor = to_minor(p.amount, currency)
        on = (p.occurred_at or datetime.now()).date()
        rate = await self.fx.get_rate(on, currency, base_currency)
        base_amount_minor = convert(amount_minor, currency, base_currency, rate=rate)

        return ResolvedTransaction(
            occurred_at=p.occurred_at or datetime.now(),
            account_id=account_id,
            category_id=cat_id,
            kind=p.kind,
            amount_minor=amount_minor,
            currency=currency,
            base_amount_minor=base_amount_minor,
            fx_rate=rate,
            base_currency=base_currency,
            merchant=p.merchant,
            note=p.note,
            confidence=confidence,
            ambiguities=ambiguities,
        )
