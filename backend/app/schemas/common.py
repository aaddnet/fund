from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator


class RateFetchRequest(BaseModel):
    base: str = "USD"
    quote: str = "CNY"
    snapshot_date: date

    @field_validator("base", "quote")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper()

class RateManualRequest(BaseModel):
    base: str
    quote: str
    rate: Decimal
    snapshot_date: date

    @field_validator("base", "quote")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper()


class PriceFetchRequest(BaseModel):
    assets: list[str]
    snapshot_date: date

    @field_validator("assets")
    @classmethod
    def normalize_assets(cls, v: list[str]) -> list[str]:
        return [a.strip().upper() for a in v if a.strip()]


class NavCalcRequest(BaseModel):
    nav_date: date
    force: bool = False


class CashPositionUpsertRequest(BaseModel):
    account_id: int
    currency: str
    amount: Decimal
    snapshot_date: date
    note: Optional[str] = None

class AccountCreateRequest(BaseModel):
    holder_name: Optional[str] = None
    broker: str
    account_no: str
    # V4.1: IB multi-currency margin account fields
    base_currency: Optional[str] = None
    account_capabilities: Optional[str] = None   # "Margin" / "Cash" / "Portfolio Margin"
    is_margin: Optional[bool] = None
    master_account_no: Optional[str] = None
    ib_account_no: Optional[str] = None           # e.g. U8312308

class AccountUpdateRequest(BaseModel):
    holder_name: Optional[str] = None
    broker: Optional[str] = None
    account_no: Optional[str] = None
    # V4.1: IB multi-currency margin account fields
    base_currency: Optional[str] = None
    account_capabilities: Optional[str] = None
    is_margin: Optional[bool] = None
    master_account_no: Optional[str] = None
    ib_account_no: Optional[str] = None

class TransactionCreateRequest(BaseModel):
    """V4.2: Manual transaction entry -- all transaction types."""
    account_id: int
    tx_category: str                    # TRADE / CASH / FX / LENDING / ACCRUAL / CORPORATE
    tx_type: str                        # see TxType enum in spec
    trade_date: date
    currency: str
    # Optional common fields
    settle_date: Optional[date] = None
    description: Optional[str] = None
    source: Optional[str] = "manual"
    # Amount fields (v4.2)
    gross_amount: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    transaction_fee: Optional[Decimal] = None
    other_fee: Optional[Decimal] = None
    # Legacy
    amount: Optional[Decimal] = None
    fee: Optional[Decimal] = None
    # TRADE fields
    asset_code: Optional[str] = None
    asset_name: Optional[str] = None
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    isin: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None
    # Option fields
    option_underlying: Optional[str] = None
    option_expiry: Optional[date] = None
    option_strike: Optional[Decimal] = None
    option_type: Optional[str] = None
    option_multiplier: Optional[int] = None
    # FX fields
    fx_from_currency: Optional[str] = None
    fx_from_amount: Optional[Decimal] = None
    fx_to_currency: Optional[str] = None
    fx_to_amount: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    # Lending fields
    lending_asset_code: Optional[str] = None
    lending_quantity: Optional[Decimal] = None
    lending_rate_pct: Optional[Decimal] = None
    collateral_amount: Optional[Decimal] = None
    # Accrual fields
    accrual_type: Optional[str] = None
    accrual_period_start: Optional[date] = None
    accrual_period_end: Optional[date] = None
    is_accrual_reversal: Optional[bool] = None
    # Corporate action fields
    corporate_ratio: Optional[Decimal] = None
    corporate_new_code: Optional[str] = None
    # Internal transfer
    counterparty_account: Optional[str] = None
    tx_subtype: Optional[str] = None


class TransactionUpdateRequest(BaseModel):
    """V4.2: Edit an existing transaction (all fields optional)."""
    tx_category: Optional[str] = None
    tx_type: Optional[str] = None
    trade_date: Optional[date] = None
    settle_date: Optional[date] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    gross_amount: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    transaction_fee: Optional[Decimal] = None
    other_fee: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    fee: Optional[Decimal] = None
    asset_code: Optional[str] = None
    asset_name: Optional[str] = None
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    isin: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None
    option_underlying: Optional[str] = None
    option_expiry: Optional[date] = None
    option_strike: Optional[Decimal] = None
    option_type: Optional[str] = None
    option_multiplier: Optional[int] = None
    fx_from_currency: Optional[str] = None
    fx_from_amount: Optional[Decimal] = None
    fx_to_currency: Optional[str] = None
    fx_to_amount: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    lending_asset_code: Optional[str] = None
    lending_quantity: Optional[Decimal] = None
    lending_rate_pct: Optional[Decimal] = None
    collateral_amount: Optional[Decimal] = None
    accrual_type: Optional[str] = None
    accrual_period_start: Optional[date] = None
    accrual_period_end: Optional[date] = None
    is_accrual_reversal: Optional[bool] = None
    corporate_ratio: Optional[Decimal] = None
    corporate_new_code: Optional[str] = None
    counterparty_account: Optional[str] = None
    tx_subtype: Optional[str] = None


class AuthUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    client_scope_id: Optional[int] = None
    display_name: Optional[str] = None
    is_active: bool = True

class AuthPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class AuthPasswordResetRequest(BaseModel):
    new_password: str

class AuthUserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    client_scope_id: Optional[int] = None
    is_active: Optional[bool] = None


class NavRebuildRequest(BaseModel):
    start_date: date
    end_date: date
    frequency: str = "quarterly"  # 'quarterly' / 'yearly' / 'monthly'
    force: bool = False


class PriceManualRequest(BaseModel):
    asset_code: str
    price_usd: Decimal
    snapshot_date: date

    @field_validator("asset_code")
    @classmethod
    def normalize_asset(cls, v: str) -> str:
        return v.strip().upper()
