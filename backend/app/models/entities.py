"""
Investment Portfolio Tracker — Data Models (v1)

Tables:
  account, transaction, position, cash_position,
  import_batch, asset_price, exchange_rate,
  nav_record, asset_snapshot,
  auth_user, auth_session, audit_log, scheduler_job_run
"""
import json

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from app.db import Base


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ── Portfolio Core ────────────────────────────────────────────────────────

class Account(Base, TimestampMixin):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("broker", "account_no", name="uq_account_broker_account_no"),
    )
    id = Column(Integer, primary_key=True)
    holder_name = Column(String(200))
    broker = Column(String(100), nullable=False)
    account_no = Column(String(100), nullable=False)
    base_currency = Column(String(10), nullable=True, default="USD")
    account_capabilities = Column(String(50), nullable=True)
    is_margin = Column(Boolean, nullable=True, default=False)
    master_account_no = Column(String(50), nullable=True)
    ib_account_no = Column(String(50), nullable=True)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transaction"
    __table_args__ = (
        Index("idx_transaction_account_id_trade_date", "account_id", "trade_date"),
        Index("ix_tx_account_date", "account_id", "trade_date"),
        Index("ix_tx_asset_date", "account_id", "asset_code", "trade_date"),
        Index("ix_tx_category_date", "account_id", "tx_category", "trade_date"),
        Index("ix_tx_type", "tx_type"),
        Index("ix_tx_category", "tx_category"),
        Index("ix_tx_asset", "asset_code"),
    )
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    asset_code = Column(String(50))
    asset_name = Column(String(200), nullable=True)
    asset_type = Column(String(20), nullable=True)
    quantity = Column(Numeric(24, 8))
    price = Column(Numeric(24, 8))
    currency = Column(String(10), nullable=False, default="USD")
    amount = Column(Numeric(24, 8))
    fee = Column(Numeric(24, 8), default=0)
    tx_type = Column(String(50), nullable=False)
    tx_category = Column(String(30))
    source = Column(String(30), default="manual")
    batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=True)
    description = Column(Text, nullable=True)
    realized_pnl = Column(Numeric(24, 8), nullable=True)
    settle_date = Column(Date, nullable=True)
    # Fee decomposition
    tx_subtype = Column(String(30), nullable=True)
    gross_amount = Column(Numeric(24, 8), nullable=True)
    commission = Column(Numeric(24, 8), nullable=True)
    transaction_fee = Column(Numeric(24, 8), nullable=True)
    other_fee = Column(Numeric(24, 8), nullable=True)
    # Asset metadata
    isin = Column(String(20), nullable=True)
    exchange = Column(String(10), nullable=True)
    close_price = Column(Numeric(24, 8), nullable=True)
    cost_basis = Column(Numeric(24, 8), nullable=True)
    # Option fields
    option_underlying = Column(String(20), nullable=True)
    option_expiry = Column(Date, nullable=True)
    option_strike = Column(Numeric(24, 8), nullable=True)
    option_type = Column(String(4), nullable=True)
    option_multiplier = Column(Integer, nullable=True)
    # FX fields
    fx_from_currency = Column(String(10), nullable=True)
    fx_from_amount = Column(Numeric(24, 8), nullable=True)
    fx_to_currency = Column(String(10), nullable=True)
    fx_to_amount = Column(Numeric(24, 8), nullable=True)
    fx_rate = Column(Numeric(18, 8), nullable=True)
    # Accrual
    accrual_period_start = Column(Date, nullable=True)
    accrual_period_end = Column(Date, nullable=True)
    is_accrual_reversal = Column(Boolean, nullable=True, default=False)
    # Corporate action
    corporate_ratio = Column(Numeric(10, 6), nullable=True)
    corporate_new_code = Column(String(50), nullable=True)
    # Lending
    lending_asset_code = Column(String(50), nullable=True)
    lending_quantity = Column(Numeric(24, 8), nullable=True)
    lending_rate_pct = Column(Numeric(10, 6), nullable=True)
    # Internal
    counterparty_account = Column(String(50), nullable=True)
    created_by = Column(Integer, ForeignKey("auth_user.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("auth_user.id"), nullable=True)


class Position(Base, TimestampMixin):
    __tablename__ = "position"
    __table_args__ = (
        UniqueConstraint("account_id", "asset_code", "snapshot_date", name="uq_position_account_asset_date"),
    )
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    asset_code = Column(String(50), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    average_cost = Column(Numeric(24, 8))
    snapshot_date = Column(Date, nullable=False)


class CashPosition(Base, TimestampMixin):
    __tablename__ = "cash_position"
    __table_args__ = (UniqueConstraint("account_id", "currency", "snapshot_date", name="uq_cash_position_account_currency_date"),)
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    currency = Column(String(10), nullable=False)
    amount = Column(Numeric(24, 8), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    note = Column(String(255))
    source_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=True)


# ── Import ────────────────────────────────────────────────────────────────

class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batch"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    source = Column(String(50), nullable=False)
    filename = Column(String(255))
    file_hash = Column(String(64))
    status = Column(String(30), nullable=False, default="uploaded")
    row_count = Column(Integer, nullable=False, default=0)
    parsed_count = Column(Integer, nullable=False, default=0)
    confirmed_count = Column(Integer, nullable=False, default=0)
    parsed_data = Column(Text)
    failed_reason = Column(Text)
    overlap_info = Column(Text)
    pending_deposits = Column(Text)


# ── Pricing & FX ──────────────────────────────────────────────────────────

class AssetPrice(Base, TimestampMixin):
    __tablename__ = "asset_price"
    __table_args__ = (UniqueConstraint("asset_code", "snapshot_date"),)
    id = Column(Integer, primary_key=True)
    asset_code = Column(String(50), nullable=False)
    price_usd = Column(Numeric(24, 8), nullable=False)
    source = Column(String(20), nullable=False)
    snapshot_date = Column(Date, nullable=False)


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rate"
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "rate_date", name="uq_exchange_rate_pair_date"),)
    id = Column(Integer, primary_key=True)
    base_currency = Column(String(10), nullable=False)
    quote_currency = Column(String(10), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    rate_date = Column(Date, nullable=False)
    source = Column(String(20), nullable=False, default="manual")


# ── Portfolio Snapshots (was NAV) ─────────────────────────────────────────

class NAVRecord(Base, TimestampMixin):
    """Portfolio value snapshot — total assets across all accounts on a given date."""
    __tablename__ = "nav_record"
    __table_args__ = (UniqueConstraint("nav_date", name="uq_nav_record_date"),)
    id = Column(Integer, primary_key=True)
    nav_date = Column(Date, nullable=False)
    total_assets_usd = Column(Numeric(24, 8), nullable=False)
    is_locked = Column(Boolean, nullable=False, default=False)
    cash_total_usd = Column(Numeric(24, 8))
    positions_total_usd = Column(Numeric(24, 8))


class AssetSnapshot(Base, TimestampMixin):
    __tablename__ = "asset_snapshot"
    __table_args__ = (Index("idx_asset_snapshot_nav_record_id", "nav_record_id"),)
    id = Column(Integer, primary_key=True)
    nav_record_id = Column(Integer, ForeignKey("nav_record.id"), nullable=False)
    asset_code = Column(String(50), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    price_usd = Column(Numeric(24, 8), nullable=False)
    value_usd = Column(Numeric(24, 8), nullable=False)
    currency = Column(String(10))
    price_native = Column(Numeric(24, 8))
    value_native = Column(Numeric(24, 8))
    fx_rate_to_usd = Column(Numeric(24, 8))
    account_ids = Column(Text)


# ── Auth & Audit ──────────────────────────────────────────────────────────

class AuthUser(Base, TimestampMixin):
    __tablename__ = "auth_user"
    __table_args__ = (UniqueConstraint("username"), Index("idx_auth_user_role", "role"),)
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    display_name = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True))
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    last_failed_login_at = Column(DateTime(timezone=True))
    locked_until = Column(DateTime(timezone=True))


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_session"
    __table_args__ = (
        UniqueConstraint("session_token_hash"),
        UniqueConstraint("refresh_token_hash"),
        Index("idx_auth_session_user_id", "user_id"),
        Index("idx_auth_session_active_expires_at", "revoked_at", "expires_at"),
        Index("idx_auth_session_refresh_expires_at", "refresh_expires_at"),
        Index("idx_auth_session_refresh_family", "refresh_family_id"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("auth_user.id"), nullable=False)
    session_token_hash = Column(String(255), nullable=False)
    refresh_token_hash = Column(String(255), nullable=False)
    refresh_parent_hash = Column(String(255))
    refresh_family_id = Column(String(64))
    refresh_reused_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True))
    refreshed_at = Column(DateTime(timezone=True))


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_action_created_at", "action", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    actor_role = Column(String(50), nullable=False)
    actor_id = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100))
    status = Column(String(30), nullable=False, default="success")
    detail_json = Column(Text, nullable=False, default="{}")

    @property
    def detail(self):
        try:
            return json.loads(self.detail_json or "{}")
        except json.JSONDecodeError:
            return {}


class SchedulerJobRun(Base, TimestampMixin):
    __tablename__ = "scheduler_job_run"
    __table_args__ = (Index("idx_scheduler_job_run_name_started_at", "job_name", "started_at"),)
    id = Column(Integer, primary_key=True)
    job_name = Column(String(100), nullable=False)
    trigger_source = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    message = Column(Text)
    detail_json = Column(Text, nullable=False, default="{}")
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True))

    @property
    def detail(self):
        try:
            return json.loads(self.detail_json or "{}")
        except json.JSONDecodeError:
            return {}
