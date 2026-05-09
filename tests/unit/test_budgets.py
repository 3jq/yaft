import datetime as dt
import pytest
from yaft.domain.budgets import month_window, spent_minor, period_key
from yaft.db.models import Account, Category, Currency, Setting, Transaction


def test_month_window():
    s, e = month_window(dt.date(2026, 5, 9))
    assert s == dt.datetime(2026, 5, 1)
    assert e == dt.datetime(2026, 6, 1)
    s, e = month_window(dt.date(2026, 12, 31))
    assert e == dt.datetime(2027, 1, 1)


def test_period_key():
    assert period_key(dt.date(2026, 5, 9)) == "2026-05"


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Cash", kind="cash", currency="USD"),
        Category(id=1, name="Food", kind="expense"),
        Category(id=2, name="Lunch", parent_id=1, kind="expense"),
        Category(id=3, name="Transport", kind="expense"),
        Setting(key="base_currency", value="USD"),
    ])
    for amt, cat, when in [(1000, 1, dt.datetime(2026, 5, 2)), (2000, 2, dt.datetime(2026, 5, 5)),
                           (5000, 3, dt.datetime(2026, 5, 8)), (4000, 1, dt.datetime(2026, 4, 30))]:
        session.add(Transaction(group_id="g", occurred_at=when, account_id=1, category_id=cat,
                                kind="expense", amount_minor=amt, currency="USD",
                                base_amount_minor=amt, fx_rate=1.0))
    await session.commit()
    return session


async def test_spent_minor_includes_descendants(seeded):
    s = await spent_minor(seeded, category_id=1, on=dt.date(2026, 5, 9))
    assert s == 3000  # 1000 (Food) + 2000 (Lunch under Food)


async def test_spent_minor_excludes_other_categories(seeded):
    s = await spent_minor(seeded, category_id=3, on=dt.date(2026, 5, 9))
    assert s == 5000


async def test_spent_minor_excludes_other_months(seeded):
    s = await spent_minor(seeded, category_id=1, on=dt.date(2026, 4, 15))
    assert s == 4000


# Task 2 tests appended below
import json


async def test_due_alerts_fires_each_threshold_once(seeded):
    from yaft.domain.budgets import due_alerts, mark_fired
    from yaft.db.models import Budget, AlertFired
    seeded.add(Budget(id=1, category_id=1, amount_minor=2500, currency="USD",
                      alert_thresholds='[0.5,0.8,1.0]'))
    await seeded.commit()
    today = dt.date(2026, 5, 9)  # Food spent = 3000 → 120% of 2500
    alerts = await due_alerts(seeded, today)
    fractions = sorted(a.threshold for a in alerts)
    assert fractions == [0.5, 0.8, 1.0]
    for a in alerts:
        await mark_fired(seeded, a.budget_id, today, a.threshold)
    await seeded.commit()
    again = await due_alerts(seeded, today)
    assert again == []
