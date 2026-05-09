from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yaft.bot.parser_text import ParsedTransaction
from yaft.db.models import Account, Category, Setting
from yaft.domain.fx import FxService
from yaft.domain.money import convert, to_minor


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

        if p.kind == "transfer":
            cat_id, c_amb, c_conf = None, [], 1.0
        else:
            cat_id, c_amb, c_conf = await self._resolve_category(p.category, p.kind)
        ambiguities += c_amb
        confidence *= c_conf

        amount_minor = to_minor(p.amount, currency)
        on = (p.occurred_at or datetime.now()).date()
        rate = await self.fx.get_rate(on, currency, base_currency)
        base_amount_minor = convert(amount_minor, currency, base_currency, rate=rate)

        # Transfer target
        transfer_to_id: int | None = None
        if p.kind == "transfer":
            if p.transfer_to_account:
                transfer_to_id, t_amb, t_conf = await self._resolve_account(p.transfer_to_account)
                ambiguities += t_amb
                confidence *= t_conf
            else:
                ambiguities.append("transfer target not specified")
                confidence *= 0.5

        # Splits → resolve each leg's category in original currency.
        # Sanity guard: if split amounts don't sum to the parent (within rounding), the LLM
        # likely included the total as one of the splits. Drop the splits and fall back to a
        # single-leg expense; flag the ambiguity.
        resolved_splits: list[dict] | None = None
        if p.splits:
            split_minors = [to_minor(s["amount"], currency) for s in p.splits]
            split_sum = sum(split_minors)
            tolerance = max(2, amount_minor // 100)  # 1% or 2 minor units, whichever larger
            if abs(split_sum - amount_minor) > tolerance:
                ambiguities.append(
                    f"split amounts ({split_sum}) don't match total ({amount_minor}); "
                    "splits dropped — recorded as single line"
                )
                confidence *= 0.6
            else:
                resolved_splits = []
                for s, m in zip(p.splits, split_minors, strict=True):
                    cat_id_s, amb_s, _ = await self._resolve_category(s.get("category"), "expense")
                    ambiguities += amb_s
                    resolved_splits.append({
                        "category_id": cat_id_s,
                        "amount_minor": m,
                        "note": s.get("note"),
                    })

        return ResolvedTransaction(
            occurred_at=p.occurred_at or datetime.now(),
            account_id=account_id, category_id=cat_id,
            kind=p.kind, amount_minor=amount_minor, currency=currency,
            base_amount_minor=base_amount_minor, fx_rate=rate, base_currency=base_currency,
            merchant=p.merchant, note=p.note,
            confidence=confidence, ambiguities=ambiguities,
            splits=resolved_splits, transfer_to_account_id=transfer_to_id,
        )
