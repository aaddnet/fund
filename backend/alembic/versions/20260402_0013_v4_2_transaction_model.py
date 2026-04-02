"""v4.2 transaction model: new fields for manual entry, lending, accruals, corporate actions

Revision ID: 20260402_0013
Revises: 20260402_0012
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260402_0013"
down_revision = "20260402_0012"
branch_labels = None
depends_on = None


def upgrade():
    # ── Securities lending (renamed/new fields) ──────────────────────────
    op.add_column("transaction", sa.Column("lending_asset_code", sa.String(50), nullable=True))
    op.add_column("transaction", sa.Column("lending_quantity", sa.Numeric(24, 8), nullable=True))
    op.add_column("transaction", sa.Column("lending_rate_pct", sa.Numeric(10, 6), nullable=True))

    # ── Accrual reversal flag ─────────────────────────────────────────────
    op.add_column("transaction", sa.Column("is_accrual_reversal", sa.Boolean(), nullable=True, server_default="false"))

    # ── Corporate action: new code after split/spinoff ────────────────────
    op.add_column("transaction", sa.Column("corporate_new_code", sa.String(50), nullable=True))

    # ── Audit: who created/updated ────────────────────────────────────────
    op.add_column("transaction", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column("transaction", sa.Column("updated_by", sa.Integer(), nullable=True))

    # ── Indexes for common query patterns ─────────────────────────────────
    op.create_index("ix_tx_category", "transaction", ["account_id", "tx_category", "trade_date"])
    op.create_index("ix_tx_asset", "transaction", ["account_id", "asset_code", "trade_date"])


def downgrade():
    op.drop_index("ix_tx_asset", "transaction")
    op.drop_index("ix_tx_category", "transaction")
    op.drop_column("transaction", "updated_by")
    op.drop_column("transaction", "created_by")
    op.drop_column("transaction", "corporate_new_code")
    op.drop_column("transaction", "is_accrual_reversal")
    op.drop_column("transaction", "lending_rate_pct")
    op.drop_column("transaction", "lending_quantity")
    op.drop_column("transaction", "lending_asset_code")
