"""seed: currencies, default account, default categories, settings"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CURRENCIES = [
    ("USD","US Dollar"),("EUR","Euro"),("GBP","Pound Sterling"),("AED","UAE Dirham"),
    ("RUB","Russian Ruble"),("CHF","Swiss Franc"),("JPY","Japanese Yen"),
]
CATEGORIES = [
    # name, parent (None=top), kind, emoji
    ("Food", None, "expense", "🍽"),
    ("Lunch", "Food", "expense", None),
    ("Groceries", "Food", "expense", "🛒"),
    ("Transport", None, "expense", "🚗"),
    ("Housing", None, "expense", "🏠"),
    ("Utilities", None, "expense", "💡"),
    ("Health", None, "expense", "💊"),
    ("Entertainment", None, "expense", "🎬"),
    ("Subscriptions", None, "expense", "🔁"),
    ("Misc", None, "expense", "🧾"),
    ("Salary", None, "income", "💰"),
    ("Other Income", None, "income", "📥"),
    ("Transfer", None, "transfer", "↔️"),
]

def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO currencies(code,name) VALUES (:c,:n)"),
                 [{"c": c, "n": n} for c, n in CURRENCIES])
    name_to_id = {}
    for name, parent, kind, emoji in CATEGORIES:
        parent_id = name_to_id.get(parent) if parent else None
        sql = sa.text(
            "INSERT INTO categories(name,parent_id,kind,emoji,archived)"
            " VALUES(:n,:p,:k,:e,0)"
        )
        result = bind.execute(sql, {"n": name, "p": parent_id, "k": kind, "e": emoji})
        name_to_id[name] = result.lastrowid
    bind.execute(sa.text(
        "INSERT INTO accounts(name,kind,currency,opening_balance_minor,archived)"
        " VALUES('Cash','cash','USD',0,0)"
    ))
    settings = [("base_currency", "USD"), ("timezone", "UTC"), ("default_account_id", "1"),
                ("alert_thresholds_default", "[0.8,1.0]")]
    bind.execute(sa.text("INSERT INTO settings(key,value) VALUES (:k,:v)"),
                 [{"k": k, "v": v} for k, v in settings])

def downgrade() -> None:
    bind = op.get_bind()
    for t in ("settings", "accounts", "categories", "currencies"):
        bind.execute(sa.text(f"DELETE FROM {t}"))
