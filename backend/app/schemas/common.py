from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class RateFetchRequest(BaseModel):
    base: str = "USD"
    quote: str = "CNY"
    snapshot_date: date


class PriceFetchRequest(BaseModel):
    assets: list[str]
    snapshot_date: date


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


class ImportConfirmRequest(BaseModel):
    batch_id: Optional[int] = None


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
