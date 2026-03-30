"""Add pending_deposits column to import_batch for capital-event confirmation workflow."""

revision = "20260331_0009"
down_revision = "20260330_0008"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "import_batch",
        sa.Column("pending_deposits", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_batch", "pending_deposits")
