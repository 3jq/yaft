import datetime as dt
import pytest
from finance_app.domain.goals import progress_minor, projected_hit_date
from finance_app.db.models import Account, Currency, Goal, GoalContribution, Setting, Transaction


@pytest.fixture
async def seeded(session):
    session.add_all([
        Currency(code="USD", name="USD"),
        Account(id=1, name="Savings", kind="savings", currency="USD", opening_balance_minor=10000),
        Setting(key="base_currency", value="USD"),
    ])
    # +20000 income on day 1 of period, +10000 on day 30
    session.add_all([
        Transaction(group_id="g", occurred_at=dt.datetime(2026, 3, 1),
                    account_id=1, kind="income", amount_minor=20000, currency="USD",
                    base_amount_minor=20000, fx_rate=1.0),
        Transaction(group_id="g", occurred_at=dt.datetime(2026, 3, 30),
                    account_id=1, kind="income", amount_minor=10000, currency="USD",
                    base_amount_minor=10000, fx_rate=1.0),
    ])
    await session.commit()
    return session


async def test_account_linked_progress(seeded):
    g = Goal(id=1, name="Emergency", target_minor=100000, currency="USD",
             progress_mode="account_linked", account_id=1)
    seeded.add(g)
    await seeded.commit()
    assert await progress_minor(seeded, g) == 40000  # 10000 + 20000 + 10000


async def test_contribution_tagged_progress(seeded):
    g = Goal(id=2, name="Trip", target_minor=50000, currency="USD",
             progress_mode="contribution_tagged", account_id=None)
    seeded.add(g)
    await seeded.flush()
    seeded.add(GoalContribution(goal_id=2, transaction_id=1, amount_minor=15000))
    await seeded.commit()
    assert await progress_minor(seeded, g) == 15000


async def test_projection_extrapolates(seeded):
    g = Goal(id=3, name="X", target_minor=100000, currency="USD",
             progress_mode="account_linked", account_id=1)
    seeded.add(g)
    await seeded.commit()
    today = dt.date(2026, 4, 1)
    eta = await projected_hit_date(seeded, g, today)
    assert eta is not None
    assert eta > today
