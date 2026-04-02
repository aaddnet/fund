"""v1_simplify: Remove fund management tables, simplify account/nav models

Revision ID: 20260402_0014
Revises: 20260402_0013
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260402_0014"
down_revision = "20260402_0013"
branch_labels = None
depends_on = None


def upgrade():
    # ── Drop fund-management tables (reverse dependency order) ────────────
    op.drop_table("client_capital_account")
    op.drop_table("share_register")
    op.drop_table("fee_record")
    op.drop_table("share_transaction")
    op.drop_table("pdf_import_batch")
    op.drop_table("cash_collateral")
    op.drop_table("accrual")

    # Drop account.fund_id FK and column
    op.drop_constraint("uq_account_fund_account_no", "account", type_="unique")
    op.drop_constraint("account_fund_id_fkey", "account", type_="foreignkey")
    op.drop_column("account", "fund_id")
    op.create_unique_constraint("uq_account_broker_account_no", "account", ["broker", "account_no"])

    # Simplify nav_record: drop fund_id and share-related columns
    op.drop_constraint("nav_record_fund_id_nav_date_key", "nav_record", type_="unique")
    op.drop_constraint("nav_record_fund_id_fkey", "nav_record", type_="foreignkey")
    op.drop_column("nav_record", "fund_id")
    op.drop_column("nav_record", "total_shares")
    op.drop_column("nav_record", "nav_per_share")
    op.create_unique_constraint("uq_nav_record_date", "nav_record", ["nav_date"])

    # Drop auth_user.client_scope_id
    try:
        op.drop_constraint("auth_user_client_scope_id_fkey", "auth_user", type_="foreignkey")
    except Exception:
        pass  # May not exist as named constraint
    try:
        op.drop_index("idx_audit_log_client_scope_id", table_name="audit_log")
    except Exception:
        pass
    op.drop_column("auth_user", "client_scope_id")
    op.drop_column("audit_log", "client_scope_id")

    # Drop client table last (was referenced by auth_user)
    op.drop_table("client")
    # Drop fund table last (was referenced by account, nav_record)
    op.drop_table("fund")


def downgrade():
    # Recreating all dropped tables and columns is not supported for v1 migration.
    raise NotImplementedError("Downgrade from v1 simplification is not supported. Restore from backup.")
