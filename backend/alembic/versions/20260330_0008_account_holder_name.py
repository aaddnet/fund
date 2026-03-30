"""Replace account.client_id FK with holder_name text field."""

revision = "20260330_0008"
down_revision = "20260330_0007"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Add holder_name column
    op.add_column("account", sa.Column("holder_name", sa.String(200), nullable=True))

    # Migrate existing client names into holder_name
    op.execute("""
        UPDATE account SET holder_name = c.name
        FROM client c WHERE account.client_id = c.id
    """)

    # Drop the index and FK on client_id, then drop the column
    op.drop_index("idx_account_client_id", table_name="account")
    op.drop_constraint("account_client_id_fkey", table_name="account", type_="foreignkey")
    op.drop_column("account", "client_id")


def downgrade() -> None:
    op.add_column("account", sa.Column("client_id", sa.Integer(), nullable=True))
    op.create_foreign_key("account_client_id_fkey", "account", "client", ["client_id"], ["id"])
    op.create_index("idx_account_client_id", "account", ["client_id"])
    op.drop_column("account", "holder_name")
