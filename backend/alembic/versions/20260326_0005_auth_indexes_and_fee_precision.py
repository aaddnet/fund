"""auth table indexes and fee record precision widening

Revision ID: 20260326_0003
Revises: 20260317_0002
Create Date: 2026-03-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260326_0005"
down_revision = "20260317_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Auth session indexes: user_id lookup (all sessions for a user) and expires_at cleanup
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index("ix_auth_session_expires_at", "auth_session", ["expires_at"])

    # Auth user: explicit index on username for fast lookup (UniqueConstraint already creates one
    # in PostgreSQL but we add a named index for clarity and SQLite compatibility)
    op.create_index("ix_auth_user_username", "auth_user", ["username"], unique=True)

    # Widen fee_record percentage columns from Numeric(12,6) to Numeric(18,8) for
    # higher-precision annualised return calculations (avoid truncation on small rates).
    # SQLite silently accepts this ALTER; PostgreSQL applies the new precision.
    try:
        op.alter_column("fee_record", "gross_return", type_=sa.Numeric(18, 8), existing_nullable=False)
        op.alter_column("fee_record", "fee_rate", type_=sa.Numeric(18, 8), existing_nullable=False)
        op.alter_column("fee_record", "annual_return_pct", type_=sa.Numeric(18, 8), existing_nullable=True)
        op.alter_column("fee_record", "excess_return_pct", type_=sa.Numeric(18, 8), existing_nullable=True)
    except Exception:
        # SQLite does not support ALTER COLUMN type changes; no-op in test environment.
        pass


def downgrade() -> None:
    op.drop_index("ix_auth_user_username", table_name="auth_user")
    op.drop_index("ix_auth_session_expires_at", table_name="auth_session")
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")

    try:
        op.alter_column("fee_record", "excess_return_pct", type_=sa.Numeric(12, 6), existing_nullable=True)
        op.alter_column("fee_record", "annual_return_pct", type_=sa.Numeric(12, 6), existing_nullable=True)
        op.alter_column("fee_record", "fee_rate", type_=sa.Numeric(12, 6), existing_nullable=False)
        op.alter_column("fee_record", "gross_return", type_=sa.Numeric(12, 6), existing_nullable=False)
    except Exception:
        pass
