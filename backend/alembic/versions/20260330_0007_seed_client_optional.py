"""Make client_id nullable on share_transaction and share_register for fund-level seed capital."""

revision = "20260330_0007"
down_revision = "20260330_0006"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.alter_column("share_transaction", "client_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("share_register", "client_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("share_register", "client_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("share_transaction", "client_id", existing_type=sa.Integer(), nullable=False)
