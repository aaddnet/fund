"""refresh token family and reuse detection metadata

Revision ID: 20260317_0004
Revises: 20260317_0003
Create Date: 2026-03-17 22:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_session", sa.Column("refresh_parent_hash", sa.String(length=255), nullable=True))
    op.add_column("auth_session", sa.Column("refresh_family_id", sa.String(length=64), nullable=True))
    op.add_column("auth_session", sa.Column("refresh_reused_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_auth_session_refresh_family", "auth_session", ["refresh_family_id"], unique=False)

    op.execute("UPDATE auth_session SET refresh_family_id = substr(refresh_token_hash, 1, 64) WHERE refresh_family_id IS NULL AND refresh_token_hash IS NOT NULL")


def downgrade() -> None:
    op.drop_index("idx_auth_session_refresh_family", table_name="auth_session")
    op.drop_column("auth_session", "refresh_reused_at")
    op.drop_column("auth_session", "refresh_family_id")
    op.drop_column("auth_session", "refresh_parent_hash")
