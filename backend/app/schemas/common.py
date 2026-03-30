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
    client_id: int
    amount_usd: Decimal
    seed_date: date

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
    client_id: Optional[int] = None
    broker: str
    account_no: str

class AccountUpdateRequest(BaseModel):
    fund_id: Optional[int] = None
    client_id: Optional[int] = None
    broker: Optional[str] = None
    account_no: Optional[str] = None

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
