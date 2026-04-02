from datetime import date
from decimal import Decimal
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
    fund_id: int
    nav_date: date
    force: bool = False


class ShareRequest(BaseModel):
    fund_id: int
    client_id: int
    tx_date: date
    amount_usd: Decimal


class FeeCalcRequest(BaseModel):
    fund_id: int
    fee_date: date

from typing import Optional

class FundCreateRequest(BaseModel):
    name: str
    base_currency: str = "USD"
    total_shares: Optional[Decimal] = None
    fund_code: Optional[str] = None
    fund_type: str = "private_equity"
    status: str = "draft"
    inception_date: Optional[date] = None
    hurdle_rate: Optional[Decimal] = None
    perf_fee_rate: Optional[Decimal] = None
    perf_fee_frequency: Optional[str] = None
    subscription_cycle: Optional[str] = None
    nav_decimal: int = 6
    share_decimal: int = 6
    description: Optional[str] = None

class FundUpdateRequest(BaseModel):
    name: Optional[str] = None
    base_currency: Optional[str] = None
    total_shares: Optional[Decimal] = None
    fund_code: Optional[str] = None
    fund_type: Optional[str] = None
    status: Optional[str] = None
    inception_date: Optional[date] = None
    first_capital_date: Optional[date] = None
    hurdle_rate: Optional[Decimal] = None
    perf_fee_rate: Optional[Decimal] = None
    perf_fee_frequency: Optional[str] = None
    subscription_cycle: Optional[str] = None
    nav_decimal: Optional[int] = None
    share_decimal: Optional[int] = None
    description: Optional[str] = None

class SeedCapitalRequest(BaseModel):
    client_id: Optional[int] = None
    amount_usd: Decimal
    seed_date: date
    shares_override: Optional[Decimal] = None  # if set, use this instead of amount ÷ 1.0

class CashPositionUpsertRequest(BaseModel):
    account_id: int
    currency: str
    amount: Decimal
    snapshot_date: date
    note: Optional[str] = None

class ClientCreateRequest(BaseModel):
    name: str
    email: Optional[str] = None

class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class AccountCreateRequest(BaseModel):
    fund_id: int
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
    fund_id: Optional[int] = None
    holder_name: Optional[str] = None
    broker: Optional[str] = None
    account_no: Optional[str] = None
    # V4.1: IB multi-currency margin account fields
    base_currency: Optional[str] = None
    account_capabilities: Optional[str] = None
    is_margin: Optional[bool] = None
    master_account_no: Optional[str] = None
    ib_account_no: Optional[str] = None

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


class DepositConfirmRequest(BaseModel):
    deposit_index: int
    client_id: Optional[int] = None
    confirm_as: str  # 'additional' or 'skip'
    note: str = ""


class NavRebuildRequest(BaseModel):
    fund_id: int
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


class PdfImportConfirmRequest(BaseModel):
    confirmed_data: Optional[dict] = None  # user-edited positions/cash/capital_events

    class Config:
        arbitrary_types_allowed = True
