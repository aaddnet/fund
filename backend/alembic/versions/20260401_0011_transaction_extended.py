"""V4: Extend Transaction table for FX, options, corporate actions, cash types.
Add is_checkpoint/checkpoint_tx_id to Position table.
Make asset_code/quantity/price nullable to support non-equity transactions."""

revision = "20260401_0011"
down_revision = "20260401_0010"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # ── Transaction: classification ──────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("tx_category", sa.String(20), nullable=False,
                  server_default="EQUITY"))
    op.add_column("transaction",
        sa.Column("settle_date", sa.Date, nullable=True))
    op.add_column("transaction",
        sa.Column("source", sa.String(20), nullable=False,
                  server_default="manual"))

    # ── Transaction: amount / description ────────────────────────────────────
    op.add_column("transaction",
        sa.Column("amount", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("description", sa.Text, nullable=True))

    # ── Transaction: asset metadata ──────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("asset_name", sa.String(200), nullable=True))
    op.add_column("transaction",
        sa.Column("asset_type", sa.String(20), nullable=True))

    # ── Transaction: realized P&L ────────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("realized_pnl", sa.Numeric(24, 8), nullable=True))

    # ── Transaction: option fields ───────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("option_underlying", sa.String(20), nullable=True))
    op.add_column("transaction",
        sa.Column("option_expiry", sa.Date, nullable=True))
    op.add_column("transaction",
        sa.Column("option_strike", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("option_type", sa.String(4), nullable=True))
    op.add_column("transaction",
        sa.Column("option_multiplier", sa.Integer, nullable=True,
                  server_default="100"))

    # ── Transaction: FX fields ───────────────────────────────────────────────
    op.add_column("transaction",
        sa.Column("fx_from_currency", sa.String(10), nullable=True))
    op.add_column("transaction",
        sa.Column("fx_from_amount", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("fx_to_currency", sa.String(10), nullable=True))
    op.add_column("transaction",
        sa.Column("fx_to_amount", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("fx_rate", sa.Numeric(18, 8), nullable=True))
    op.add_column("transaction",
        sa.Column("fx_pnl", sa.Numeric(24, 8), nullable=True))

    # ── Transaction: corporate action fields ─────────────────────────────────
    op.add_column("transaction",
        sa.Column("corporate_ratio", sa.Numeric(10, 6), nullable=True))
    op.add_column("transaction",
        sa.Column("corporate_ref_code", sa.String(50), nullable=True))

    # ── Transaction: make equity-only fields nullable ─────────────────────────
    # (CASH/FX transactions don't have asset_code/quantity/price)
    op.alter_column("transaction", "asset_code",
                    existing_type=sa.String(50), nullable=True)
    op.alter_column("transaction", "quantity",
                    existing_type=sa.Numeric(24, 8), nullable=True)
    op.alter_column("transaction", "price",
                    existing_type=sa.Numeric(24, 8), nullable=True)

    # ── Transaction: performance indexes ─────────────────────────────────────
    op.create_index("ix_transaction_account_date",
                    "transaction", ["account_id", "trade_date"])
    op.create_index("ix_transaction_asset",
                    "transaction", ["account_id", "asset_code", "trade_date"])
    op.create_index("ix_transaction_category",
                    "transaction", ["account_id", "tx_category", "trade_date"])

    # ── Position: checkpoint semantics ───────────────────────────────────────
    op.add_column("position",
        sa.Column("is_checkpoint", sa.Boolean, nullable=True,
                  server_default="true"))
    op.add_column("position",
        sa.Column("checkpoint_tx_id", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("position", "checkpoint_tx_id")
    op.drop_column("position", "is_checkpoint")

    op.drop_index("ix_transaction_category", table_name="transaction")
    op.drop_index("ix_transaction_asset", table_name="transaction")
    op.drop_index("ix_transaction_account_date", table_name="transaction")

    op.alter_column("transaction", "price",
                    existing_type=sa.Numeric(24, 8), nullable=False)
    op.alter_column("transaction", "quantity",
                    existing_type=sa.Numeric(24, 8), nullable=False)
    op.alter_column("transaction", "asset_code",
                    existing_type=sa.String(50), nullable=False)

    for col in [
        "corporate_ref_code", "corporate_ratio",
        "fx_pnl", "fx_rate", "fx_to_amount", "fx_to_currency",
        "fx_from_amount", "fx_from_currency",
        "option_multiplier", "option_type", "option_strike",
        "option_expiry", "option_underlying",
        "realized_pnl",
        "asset_type", "asset_name",
        "description", "amount",
        "source", "settle_date", "tx_category",
    ]:
        op.drop_column("transaction", col)
