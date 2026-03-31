"""V2: source_batch_id on position/cash_position, file_hash on import_batch,
source on exchange_rate, pdf_import_batch table."""

revision = "20260401_0010"
down_revision = "20260331_0009"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # FIX-03: file_hash on import_batch for dedup detection
    op.add_column("import_batch", sa.Column("file_hash", sa.String(64), nullable=True))
    op.create_index("idx_import_batch_file_hash", "import_batch", ["file_hash"])

    # FIX-02: source_batch_id on position to support complete rollback
    op.add_column("position", sa.Column("source_batch_id", sa.Integer(), sa.ForeignKey("import_batch.id"), nullable=True))
    op.create_index("idx_position_source_batch_id", "position", ["source_batch_id"])

    # FIX-02: source_batch_id on cash_position for rollback
    op.add_column("cash_position", sa.Column("source_batch_id", sa.Integer(), sa.ForeignKey("import_batch.id"), nullable=True))
    op.create_index("idx_cash_position_source_batch_id", "cash_position", ["source_batch_id"])

    # FIX-01: source column on exchange_rate to track data origin
    op.add_column("exchange_rate", sa.Column("source", sa.String(50), nullable=True))

    # PDF-01: new pdf_import_batch table for annual statement workflow
    op.create_table(
        "pdf_import_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("parsed_data", sa.Text(), nullable=True),
        sa.Column("confirmed_data", sa.Text(), nullable=True),
        sa.Column("pending_deposits", sa.Text(), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_pdf_import_batch_account_id", "pdf_import_batch", ["account_id"])
    op.create_index("idx_pdf_import_batch_status", "pdf_import_batch", ["status"])


def downgrade() -> None:
    op.drop_table("pdf_import_batch")
    op.drop_column("exchange_rate", "source")
    op.drop_index("idx_cash_position_source_batch_id", "cash_position")
    op.drop_column("cash_position", "source_batch_id")
    op.drop_index("idx_position_source_batch_id", "position")
    op.drop_column("position", "source_batch_id")
    op.drop_index("idx_import_batch_file_hash", "import_batch")
    op.drop_column("import_batch", "file_hash")
