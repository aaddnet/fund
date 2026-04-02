"""base_parser.py — shared dataclass and utilities for all platform parsers."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class TransactionRow:
    """Normalised representation of one transaction, before DB insertion."""
    trade_date: date
    tx_category: str          # TRADE / CASH / FX / LENDING / ACCRUAL / CORPORATE
    tx_type: str              # stock_buy / deposit_eft / fx_trade / …
    currency: str

    # Amount decomposition (V4.2)
    gross_amount: Optional[float] = None
    commission: Optional[float] = None
    transaction_fee: Optional[float] = None
    other_fee: Optional[float] = None

    # Asset info
    asset_code: Optional[str] = None
    asset_name: Optional[str] = None
    asset_type: Optional[str] = None      # stock / option / etf / bond
    exchange: Optional[str] = None
    isin: Optional[str] = None

    # Trade quantities
    quantity: Optional[float] = None
    price: Optional[float] = None
    cost_basis: Optional[float] = None
    realized_pnl: Optional[float] = None

    # Dates
    settle_date: Optional[date] = None
    accrual_period_end: Optional[date] = None

    # FX
    fx_from_currency: Optional[str] = None
    fx_from_amount: Optional[float] = None
    fx_to_currency: Optional[str] = None
    fx_to_amount: Optional[float] = None
    fx_rate: Optional[float] = None

    # Option
    option_underlying: Optional[str] = None
    option_expiry: Optional[date] = None
    option_strike: Optional[float] = None
    option_type: Optional[str] = None     # call / put
    option_multiplier: Optional[int] = None

    # Meta
    description: Optional[str] = None
    counterparty_account: Optional[str] = None

    # Preview flags
    is_other: bool = False    # True = pending/other — shown in 待处理 tab
    selected: bool = True     # default selected for import


def parse_csv(path: str):
    """Legacy file-path based parser for standalone use."""
    rows = []
    with Path(path).open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "date": row.get("date"),
                    "asset_code": row.get("asset_code"),
                    "quantity": float(row.get("quantity", 0) or 0),
                    "price": float(row.get("price", 0) or 0),
                    "currency": row.get("currency", "USD"),
                    "type": row.get("type", "trade"),
                    "fee": float(row.get("fee", 0) or 0),
                }
            )
    return rows


def preprocess(raw: bytes) -> bytes:
    """Identity preprocessor — returns raw bytes unchanged (generic CSV)."""
    return raw
