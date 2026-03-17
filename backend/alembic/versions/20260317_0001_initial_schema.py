"""initial schema

Revision ID: 20260317_0001
Revises: 
Create Date: 2026-03-17 15:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("total_shares", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=True),
        sa.Column("broker", sa.String(length=100), nullable=False),
        sa.Column("account_no", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "holding",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "position",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(24, 8), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "import_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="uploaded"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("preview_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("tx_type", sa.String(length=50), nullable=False),
        sa.Column("fee", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("import_batch.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "exchange_rate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_currency", sa.String(length=10), nullable=False),
        sa.Column("quote_currency", sa.String(length=10), nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("base_currency", "quote_currency", "snapshot_date"),
    )
    op.create_table(
        "asset_price",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("price_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("asset_code", "snapshot_date"),
    )
    op.create_table(
        "nav_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("nav_date", sa.Date(), nullable=False),
        sa.Column("total_assets_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("total_shares", sa.Numeric(24, 8), nullable=False),
        sa.Column("nav_per_share", sa.Numeric(24, 8), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("fund_id", "nav_date"),
    )
    op.create_table(
        "asset_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nav_record_id", sa.Integer(), sa.ForeignKey("nav_record.id"), nullable=False),
        sa.Column("asset_code", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("value_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("price_native", sa.Numeric(24, 8), nullable=True),
        sa.Column("value_native", sa.Numeric(24, 8), nullable=True),
        sa.Column("fx_rate_to_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("account_ids", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "share_transaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=False),
        sa.Column("tx_date", sa.Date(), nullable=False),
        sa.Column("tx_type", sa.String(length=20), nullable=False),
        sa.Column("amount_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("shares", sa.Numeric(24, 8), nullable=False),
        sa.Column("nav_at_date", sa.Numeric(24, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "fee_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fund.id"), nullable=False),
        sa.Column("fee_date", sa.Date(), nullable=False),
        sa.Column("gross_return", sa.Numeric(12, 6), nullable=False),
        sa.Column("fee_rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("fee_amount_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("nav_start", sa.Numeric(24, 8), nullable=True),
        sa.Column("nav_end_before_fee", sa.Numeric(24, 8), nullable=True),
        sa.Column("annual_return_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("excess_return_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("fee_base_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("nav_after_fee", sa.Numeric(24, 8), nullable=True),
        sa.Column("applied_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("client_scope_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="success"),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "scheduler_job_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("trigger_source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "auth_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("client_scope_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "auth_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth_user.id"), nullable=False),
        sa.Column("session_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_token_hash"),
    )

    op.create_index("idx_account_fund_id", "account", ["fund_id"])
    op.create_index("idx_position_snapshot_date", "position", ["snapshot_date"])
    op.create_index("idx_transaction_trade_date", "transaction", ["trade_date"])
    op.create_index("idx_exchange_rate_snapshot_date", "exchange_rate", ["snapshot_date"])
    op.create_index("idx_asset_price_snapshot_date", "asset_price", ["snapshot_date"])
    op.create_index("idx_nav_record_date", "nav_record", ["nav_date"])
    op.create_index("idx_share_transaction_date", "share_transaction", ["tx_date"])
    op.create_index("idx_share_transaction_fund_client", "share_transaction", ["fund_id", "client_id"])


def downgrade() -> None:
    op.drop_index("idx_share_transaction_fund_client", table_name="share_transaction")
    op.drop_index("idx_share_transaction_date", table_name="share_transaction")
    op.drop_index("idx_nav_record_date", table_name="nav_record")
    op.drop_index("idx_asset_price_snapshot_date", table_name="asset_price")
    op.drop_index("idx_exchange_rate_snapshot_date", table_name="exchange_rate")
    op.drop_index("idx_transaction_trade_date", table_name="transaction")
    op.drop_index("idx_position_snapshot_date", table_name="position")
    op.drop_index("idx_account_fund_id", table_name="account")

    op.drop_table("auth_session")
    op.drop_table("auth_user")
    op.drop_table("scheduler_job_run")
    op.drop_table("audit_log")
    op.drop_table("fee_record")
    op.drop_table("share_transaction")
    op.drop_table("asset_snapshot")
    op.drop_table("nav_record")
    op.drop_table("asset_price")
    op.drop_table("exchange_rate")
    op.drop_table("transaction")
    op.drop_table("import_batch")
    op.drop_table("position")
    op.drop_table("holding")
    op.drop_table("account")
    op.drop_table("client")
    op.drop_table("fund")
