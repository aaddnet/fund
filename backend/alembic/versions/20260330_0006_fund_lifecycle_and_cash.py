"""fund lifecycle fields, cash position, share register, client capital account

Revision ID: 20260330_0006
Revises: 20260326_0005
Create Date: 2026-03-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260330_0006"
down_revision = "20260326_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Fund: add lifecycle columns ---
    op.add_column("fund", sa.Column("fund_code", sa.String(20), nullable=True))
    op.add_column("fund", sa.Column("inception_date", sa.Date(), nullable=True))
    op.add_column("fund", sa.Column("first_capital_date", sa.Date(), nullable=True))
    op.add_column("fund", sa.Column("fund_type", sa.String(50), nullable=False, server_default="private_equity"))
    op.add_column("fund", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))
    op.add_column("fund", sa.Column("hurdle_rate", sa.Numeric(8, 4), nullable=True))
    op.add_column("fund", sa.Column("perf_fee_rate", sa.Numeric(8, 4), nullable=True))
    op.add_column("fund", sa.Column("perf_fee_frequency", sa.String(20), nullable=True))
    op.add_column("fund", sa.Column("subscription_cycle", sa.String(20), nullable=True))
    op.add_column("fund", sa.Column("nav_decimal", sa.Integer(), nullable=False, server_default="6"))
    op.add_column("fund", sa.Column("share_decimal", sa.Integer(), nullable=False, server_default="6"))
    op.add_column("fund", sa.Column("description", sa.Text(), nullable=True))

    # --- NAVRecord: add breakdown columns ---
    op.add_column("nav_record", sa.Column("cash_total_usd", sa.Numeric(24, 8), nullable=True))
    op.add_column("nav_record", sa.Column("positions_total_usd", sa.Numeric(24, 8), nullable=True))

    # --- New table: cash_position ---
    op.create_table(
        "cash_position",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("account_id", "currency", "snapshot_date", name="uq_cash_position_account_currency_date"),
    )
    op.create_index("idx_cash_position_account_date", "cash_position", ["account_id", "snapshot_date"])

    # --- New table: share_register ---
    op.create_table(
        "share_register",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("shares_delta", sa.Numeric(24, 8), nullable=False),
        sa.Column("shares_after", sa.Numeric(24, 8), nullable=False),
        sa.Column("nav_per_share", sa.Numeric(24, 8), nullable=False),
        sa.Column("amount_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("ref_share_tx_id", sa.Integer(), sa.ForeignKey("share_transaction.id"), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_share_register_fund_client", "share_register", ["fund_id", "client_id"])

    # --- New table: client_capital_account ---
    op.create_table(
        "client_capital_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=False),
        sa.Column("total_invested_usd", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("total_redeemed_usd", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("avg_cost_nav", sa.Numeric(24, 8), nullable=True),
        sa.Column("current_shares", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("last_updated_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "client_id", name="uq_client_capital_account_fund_client"),
    )


def downgrade() -> None:
    op.drop_table("client_capital_account")
    op.drop_index("idx_share_register_fund_client", table_name="share_register")
    op.drop_table("share_register")
    op.drop_index("idx_cash_position_account_date", table_name="cash_position")
    op.drop_table("cash_position")
    op.drop_column("nav_record", "positions_total_usd")
    op.drop_column("nav_record", "cash_total_usd")
    op.drop_column("fund", "description")
    op.drop_column("fund", "share_decimal")
    op.drop_column("fund", "nav_decimal")
    op.drop_column("fund", "subscription_cycle")
    op.drop_column("fund", "perf_fee_frequency")
    op.drop_column("fund", "perf_fee_rate")
    op.drop_column("fund", "hurdle_rate")
    op.drop_column("fund", "status")
    op.drop_column("fund", "fund_type")
    op.drop_column("fund", "first_capital_date")
    op.drop_column("fund", "inception_date")
    op.drop_column("fund", "fund_code")
