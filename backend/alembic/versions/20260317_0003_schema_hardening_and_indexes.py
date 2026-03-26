"""schema hardening and indexes

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17 20:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "sqlite"


def upgrade() -> None:
    op.execute("UPDATE auth_session SET refresh_token_hash = session_token_hash WHERE refresh_token_hash IS NULL")
    op.execute("UPDATE auth_session SET refresh_expires_at = expires_at WHERE refresh_expires_at IS NULL")
    op.execute("UPDATE auth_session SET refreshed_at = COALESCE(refreshed_at, created_at, expires_at) WHERE refreshed_at IS NULL")
    op.execute("UPDATE auth_session SET last_seen_at = COALESCE(last_seen_at, refreshed_at, created_at) WHERE last_seen_at IS NULL")
    op.execute("UPDATE auth_user SET failed_login_attempts = COALESCE(failed_login_attempts, 0)")
    op.execute("UPDATE auth_user SET password_changed_at = COALESCE(password_changed_at, last_login_at, created_at)")

    op.create_index("idx_account_client_id", "account", ["client_id"], unique=False)
    op.create_index("idx_position_account_snapshot_date", "position", ["account_id", "snapshot_date"], unique=False)
    op.create_index("idx_import_batch_account_id", "import_batch", ["account_id"], unique=False)
    op.create_index("idx_import_batch_status", "import_batch", ["status"], unique=False)
    op.create_index("idx_transaction_account_trade_date", "transaction", ["account_id", "trade_date"], unique=False)
    op.create_index("idx_transaction_import_batch_id", "transaction", ["import_batch_id"], unique=False)
    op.create_index("idx_asset_snapshot_nav_record_id", "asset_snapshot", ["nav_record_id"], unique=False)
    op.create_index("idx_share_transaction_client_date", "share_transaction", ["client_id", "tx_date"], unique=False)
    op.create_index("idx_fee_record_fund_date", "fee_record", ["fund_id", "fee_date"], unique=False)
    op.create_index("idx_audit_log_action_created_at", "audit_log", ["action", "created_at"], unique=False)
    op.create_index("idx_audit_log_client_scope_id", "audit_log", ["client_scope_id"], unique=False)
    op.create_index("idx_scheduler_job_run_name_started_at", "scheduler_job_run", ["job_name", "started_at"], unique=False)
    op.create_index("idx_auth_user_role", "auth_user", ["role"], unique=False)
    op.create_index("idx_auth_session_user_id", "auth_session", ["user_id"], unique=False)
    op.create_index("idx_auth_session_active_expires_at", "auth_session", ["revoked_at", "expires_at"], unique=False)
    op.create_index("idx_auth_session_refresh_expires_at", "auth_session", ["refresh_expires_at"], unique=False)

    if _is_sqlite():
        return

    op.alter_column("auth_session", "refresh_token_hash", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("auth_session", "refresh_expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_unique_constraint("uq_account_fund_account_no", "account", ["fund_id", "account_no"])
    op.create_unique_constraint("uq_holding_account_asset_date", "holding", ["account_id", "asset_code", "as_of_date"])
    op.create_unique_constraint("uq_position_account_asset_snapshot", "position", ["account_id", "asset_code", "snapshot_date"])
    op.create_unique_constraint("uq_fee_record_fund_fee_date", "fee_record", ["fund_id", "fee_date"])
    op.create_check_constraint("ck_import_batch_row_count_non_negative", "import_batch", "row_count >= 0")
    op.create_check_constraint("ck_import_batch_parsed_count_non_negative", "import_batch", "parsed_count >= 0")
    op.create_check_constraint("ck_import_batch_confirmed_count_non_negative", "import_batch", "confirmed_count >= 0")


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint("ck_import_batch_confirmed_count_non_negative", "import_batch", type_="check")
        op.drop_constraint("ck_import_batch_parsed_count_non_negative", "import_batch", type_="check")
        op.drop_constraint("ck_import_batch_row_count_non_negative", "import_batch", type_="check")
        op.drop_constraint("uq_fee_record_fund_fee_date", "fee_record", type_="unique")
        op.drop_constraint("uq_position_account_asset_snapshot", "position", type_="unique")
        op.drop_constraint("uq_holding_account_asset_date", "holding", type_="unique")
        op.drop_constraint("uq_account_fund_account_no", "account", type_="unique")
        op.alter_column("auth_session", "refresh_expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        op.alter_column("auth_session", "refresh_token_hash", existing_type=sa.String(length=255), nullable=True)

    op.drop_index("idx_auth_session_refresh_expires_at", table_name="auth_session")
    op.drop_index("idx_auth_session_active_expires_at", table_name="auth_session")
    op.drop_index("idx_auth_session_user_id", table_name="auth_session")
    op.drop_index("idx_auth_user_role", table_name="auth_user")
    op.drop_index("idx_scheduler_job_run_name_started_at", table_name="scheduler_job_run")
    op.drop_index("idx_audit_log_client_scope_id", table_name="audit_log")
    op.drop_index("idx_audit_log_action_created_at", table_name="audit_log")
    op.drop_index("idx_fee_record_fund_date", table_name="fee_record")
    op.drop_index("idx_share_transaction_client_date", table_name="share_transaction")
    op.drop_index("idx_asset_snapshot_nav_record_id", table_name="asset_snapshot")
    op.drop_index("idx_transaction_import_batch_id", table_name="transaction")
    op.drop_index("idx_transaction_account_trade_date", table_name="transaction")
    op.drop_index("idx_import_batch_status", table_name="import_batch")
    op.drop_index("idx_import_batch_account_id", table_name="import_batch")
    op.drop_index("idx_position_account_snapshot_date", table_name="position")
    op.drop_index("idx_account_client_id", table_name="account")
