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
