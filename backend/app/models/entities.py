import json

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from app.db import Base


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Fund(Base, TimestampMixin):
    __tablename__ = "fund"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    base_currency = Column(String(10), nullable=False, default="USD")
    total_shares = Column(Numeric(20, 6), nullable=False, default=0)


class Client(Base, TimestampMixin):
    __tablename__ = "client"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))


class Account(Base, TimestampMixin):
    __tablename__ = "account"
    id = Column(Integer, primary_key=True)
    fund_id = Column(Integer, ForeignKey("fund.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("client.id"))
    broker = Column(String(100), nullable=False)
    account_no = Column(String(100), nullable=False)


class Holding(Base, TimestampMixin):
    __tablename__ = "holding"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    asset_code = Column(String(50), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    as_of_date = Column(Date, nullable=False)


class Position(Base, TimestampMixin):
    __tablename__ = "position"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    asset_code = Column(String(50), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    average_cost = Column(Numeric(24, 8))
    currency = Column(String(10), nullable=False)
    snapshot_date = Column(Date, nullable=False)


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batch"
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    filename = Column(String(255))
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    status = Column(String(30), nullable=False, default="uploaded")
    row_count = Column(Integer, nullable=False, default=0)
    parsed_count = Column(Integer, nullable=False, default=0)
    confirmed_count = Column(Integer, nullable=False, default=0)
    failed_reason = Column(Text)
    preview_json = Column(Text, nullable=False, default="[]")
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def preview_rows(self):
        try:
            return json.loads(self.preview_json or "[]")
        except json.JSONDecodeError:
            return []


class Transaction(Base, TimestampMixin):
    __tablename__ = "transaction"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    asset_code = Column(String(50), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    price = Column(Numeric(24, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    tx_type = Column(String(50), nullable=False)
    fee = Column(Numeric(24, 8), nullable=False, default=0)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"))


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rate"
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "snapshot_date"),)
    id = Column(Integer, primary_key=True)
    base_currency = Column(String(10), nullable=False)
    quote_currency = Column(String(10), nullable=False)
    rate = Column(Numeric(20, 8), nullable=False)
    snapshot_date = Column(Date, nullable=False)


class AssetPrice(Base, TimestampMixin):
    __tablename__ = "asset_price"
    __table_args__ = (UniqueConstraint("asset_code", "snapshot_date"),)
    id = Column(Integer, primary_key=True)
    asset_code = Column(String(50), nullable=False)
    price_usd = Column(Numeric(24, 8), nullable=False)
    source = Column(String(20), nullable=False)
    snapshot_date = Column(Date, nullable=False)


class NAVRecord(Base, TimestampMixin):
    __tablename__ = "nav_record"
    __table_args__ = (UniqueConstraint("fund_id", "nav_date"),)
    id = Column(Integer, primary_key=True)
    fund_id = Column(Integer, ForeignKey("fund.id"), nullable=False)
    nav_date = Column(Date, nullable=False)
    total_assets_usd = Column(Numeric(24, 8), nullable=False)
    total_shares = Column(Numeric(24, 8), nullable=False)
    nav_per_share = Column(Numeric(24, 8), nullable=False)
    is_locked = Column(Boolean, nullable=False, default=False)


class AssetSnapshot(Base, TimestampMixin):
    __tablename__ = "asset_snapshot"
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


class ShareTransaction(Base, TimestampMixin):
    __tablename__ = "share_transaction"
    id = Column(Integer, primary_key=True)
    fund_id = Column(Integer, ForeignKey("fund.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False)
    tx_date = Column(Date, nullable=False)
    tx_type = Column(String(20), nullable=False)
    amount_usd = Column(Numeric(24, 8), nullable=False)
    shares = Column(Numeric(24, 8), nullable=False)
    nav_at_date = Column(Numeric(24, 8), nullable=False)


class FeeRecord(Base, TimestampMixin):
    __tablename__ = "fee_record"
    id = Column(Integer, primary_key=True)
    fund_id = Column(Integer, ForeignKey("fund.id"), nullable=False)
    fee_date = Column(Date, nullable=False)
    gross_return = Column(Numeric(12, 6), nullable=False)
    fee_rate = Column(Numeric(12, 6), nullable=False)
    fee_amount_usd = Column(Numeric(24, 8), nullable=False)
    nav_start = Column(Numeric(24, 8))
    nav_end_before_fee = Column(Numeric(24, 8))
    annual_return_pct = Column(Numeric(12, 6))
    excess_return_pct = Column(Numeric(12, 6))
    fee_base_usd = Column(Numeric(24, 8))
    nav_after_fee = Column(Numeric(24, 8))
    applied_date = Column(Date)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    actor_role = Column(String(50), nullable=False)
    actor_id = Column(String(100), nullable=False)
    client_scope_id = Column(Integer)
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


class AuthUser(Base, TimestampMixin):
    __tablename__ = "auth_user"
    __table_args__ = (UniqueConstraint("username"),)
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    client_scope_id = Column(Integer, ForeignKey("client.id"))
    display_name = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime(timezone=True))


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_session"
    __table_args__ = (UniqueConstraint("session_token_hash"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("auth_user.id"), nullable=False)
    session_token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True))
