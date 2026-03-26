"""auth refresh tokens and lockout

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17 16:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_user", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_user", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("auth_user", sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_user", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    op.add_column("auth_session", sa.Column("refresh_token_hash", sa.String(length=255), nullable=True))
    op.add_column("auth_session", sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_session", sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE auth_session SET refresh_token_hash = session_token_hash WHERE refresh_token_hash IS NULL")
    op.execute("UPDATE auth_session SET refresh_expires_at = expires_at WHERE refresh_expires_at IS NULL")
    op.execute("UPDATE auth_user SET password_changed_at = COALESCE(last_login_at, created_at)")

    # SQLite 测试库不支持这里的 ALTER COLUMN / add constraint，
    # 先通过数据回填+应用层 token 旋转逻辑保证新写入记录完整。


def downgrade() -> None:
    op.drop_column("auth_session", "refreshed_at")
    op.drop_column("auth_session", "refresh_expires_at")
    op.drop_column("auth_session", "refresh_token_hash")

    op.drop_column("auth_user", "locked_until")
    op.drop_column("auth_user", "last_failed_login_at")
    op.drop_column("auth_user", "failed_login_attempts")
    op.drop_column("auth_user", "password_changed_at")
