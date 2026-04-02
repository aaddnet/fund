"""V4.1: Multi-currency margin account model.

Adds:
- Transaction: tx_subtype, fee decomposition (gross_amount/commission/transaction_fee/other_fee),
               asset metadata (isin/exchange/multiplier/close_price/cost_basis),
               securities lending fields, accrual fields, counterparty_account
- Account: base_currency, account_capabilities, is_margin, master_account_no, ib_account_no
- New table: cash_collateral (securities lending positions)
- New table: accrual (interest/dividend accruals)
"""

revision = "20260402_0012"
down_revision = "20260401_0011"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # ── Transaction: subtype ──────────────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("tx_subtype", sa.String(30), nullable=True))

    # ── Transaction: fee decomposition ───────────────────────────────────────
    op.add_column("transaction",
        sa.Column("gross_amount", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("commission", sa.Numeric(24, 8), nullable=True,
                  server_default="0"))
    op.add_column("transaction",
        sa.Column("transaction_fee", sa.Numeric(24, 8), nullable=True,
                  server_default="0"))
    op.add_column("transaction",
        sa.Column("other_fee", sa.Numeric(24, 8), nullable=True,
                  server_default="0"))

    # ── Transaction: asset metadata ───────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("isin", sa.String(20), nullable=True))
    op.add_column("transaction",
        sa.Column("exchange", sa.String(20), nullable=True))
    op.add_column("transaction",
        sa.Column("multiplier", sa.Integer, nullable=True,
                  server_default="1"))
    op.add_column("transaction",
        sa.Column("close_price", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("cost_basis", sa.Numeric(24, 8), nullable=True))

    # ── Transaction: securities lending ──────────────────────────────────────
    op.add_column("transaction",
        sa.Column("lending_counterparty", sa.String(100), nullable=True))
    op.add_column("transaction",
        sa.Column("lending_rate", sa.Numeric(10, 6), nullable=True))
    op.add_column("transaction",
        sa.Column("collateral_amount", sa.Numeric(24, 8), nullable=True))

    # ── Transaction: accruals ─────────────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("accrual_type", sa.String(20), nullable=True))
    op.add_column("transaction",
        sa.Column("accrual_period_start", sa.Date, nullable=True))
    op.add_column("transaction",
        sa.Column("accrual_period_end", sa.Date, nullable=True))
    op.add_column("transaction",
        sa.Column("accrual_reversal_id", sa.Integer,
                  sa.ForeignKey("transaction.id"), nullable=True))

    # ── Transaction: internal transfer ────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("counterparty_account", sa.String(50), nullable=True))

    # ── Account: IB multi-currency margin fields ──────────────────────────────
    op.add_column("account",
        sa.Column("base_currency", sa.String(10), nullable=True,
                  server_default="USD"))
    op.add_column("account",
        sa.Column("account_capabilities", sa.String(50), nullable=True))
    op.add_column("account",
        sa.Column("is_margin", sa.Boolean, nullable=True,
                  server_default="false"))
    op.add_column("account",
        sa.Column("master_account_no", sa.String(50), nullable=True))
    op.add_column("account",
        sa.Column("ib_account_no", sa.String(50), nullable=True))

    # ── New table: cash_collateral ────────────────────────────────────────────
    op.create_table(
        "cash_collateral",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer,
                  sa.ForeignKey("account.id"), nullable=False),
        sa.Column("asset_code", sa.String(50), nullable=False),
        sa.Column("quantity_lent", sa.Numeric(24, 8), nullable=False),
        sa.Column("collateral_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("lending_rate", sa.Numeric(10, 6), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("transaction_id", sa.Integer,
                  sa.ForeignKey("transaction.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_cash_collateral_account_id",
                    "cash_collateral", ["account_id"])

    # ── New table: accrual ────────────────────────────────────────────────────
    op.create_table(
        "accrual",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer,
                  sa.ForeignKey("account.id"), nullable=False),
        sa.Column("accrual_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("accrual_date", sa.Date, nullable=False),
        sa.Column("expected_pay_date", sa.Date, nullable=True),
        sa.Column("asset_code", sa.String(50), nullable=True),
        sa.Column("is_reversed", sa.Boolean, nullable=False,
                  server_default="false"),
        sa.Column("reversal_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_accrual_account_id", "accrual", ["account_id"])
    op.create_index("idx_accrual_account_date", "accrual",
                    ["account_id", "accrual_date"])


def downgrade() -> None:
    op.drop_table("accrual")
    op.drop_table("cash_collateral")

    for col in [
        "base_currency", "account_capabilities", "is_margin",
        "master_account_no", "ib_account_no",
    ]:
        op.drop_column("account", col)

    for col in [
        "tx_subtype",
        "gross_amount", "commission", "transaction_fee", "other_fee",
        "isin", "exchange", "multiplier", "close_price", "cost_basis",
        "lending_counterparty", "lending_rate", "collateral_amount",
        "accrual_type", "accrual_period_start", "accrual_period_end",
        "accrual_reversal_id",
        "counterparty_account",
    ]:
        op.drop_column("transaction", col)
