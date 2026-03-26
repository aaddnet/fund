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
