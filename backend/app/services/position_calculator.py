"""position_calculator.py

V4: Compute holdings from Transaction events, starting from the nearest
Position checkpoint.  This is the new single-source-of-truth approach where
Transaction records are the authoritative ledger.

Usage:
    from app.services.position_calculator import calc_position, calc_all_positions
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, getcontext
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Position, Transaction

getcontext().prec = 28
logger = logging.getLogger(__name__)

ZERO = Decimal("0")

# tx_types that modify equity quantity
_EQUITY_TX_TYPES = {
    "buy", "sell",
    "buy_option", "sell_option",
    "option_expire", "option_exercise",
    "stock_split", "reverse_split",
    "rights_issue", "spinoff",
}


@dataclass
class PositionResult:
    asset_code: str
    asset_type: Optional[str]
    quantity: Decimal
    average_cost: Decimal      # weighted average (in native currency)
    total_cost: Decimal        # total cost basis
    currency: str
    realized_pnl: Decimal      # accumulated realized P&L from sells


def calc_position(
    account_id: int,
    asset_code: str,
    as_of_date: date,
    db: Session,
) -> PositionResult:
    """
    Calculate position for a single asset as of as_of_date.

    Algorithm:
    1. Find the latest Position checkpoint on or before as_of_date.
    2. Replay all Transaction events after the checkpoint date up to as_of_date.
    3. Return computed PositionResult.
    """
    asset_code_upper = asset_code.upper()

    # 1. Find nearest checkpoint
    checkpoint = (
        db.query(Position)
        .filter(
            Position.account_id == account_id,
            Position.asset_code == asset_code_upper,
            Position.snapshot_date <= as_of_date,
        )
        .order_by(Position.snapshot_date.desc())
        .first()
    )

    if checkpoint:
        base_qty = Decimal(str(checkpoint.quantity))
        base_avg = Decimal(str(checkpoint.average_cost or 0))
        base_cost = base_qty * base_avg
        base_date = checkpoint.snapshot_date
    else:
        base_qty = ZERO
        base_cost = ZERO
        base_date = date(2000, 1, 1)

    # Detect currency from checkpoint or first transaction
    currency: Optional[str] = checkpoint.currency if checkpoint else None

    # 2. Replay transactions after checkpoint
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.asset_code == asset_code_upper,
            Transaction.tx_category == "EQUITY",
            Transaction.trade_date > base_date,
            Transaction.trade_date <= as_of_date,
        )
        .order_by(Transaction.trade_date, Transaction.id)
        .all()
    )

    qty = base_qty
    cost = base_cost
    realized = ZERO
    asset_type: Optional[str] = None

    for tx in txns:
        if currency is None:
            currency = tx.currency
        if asset_type is None and tx.asset_type:
            asset_type = tx.asset_type

        tx_qty = Decimal(str(tx.quantity or 0))
        tx_price = Decimal(str(tx.price or 0))
        multiplier = Decimal(str(tx.option_multiplier or 100))

        if tx.tx_type == "buy":
            cost += tx_qty * tx_price
            qty += tx_qty

        elif tx.tx_type == "sell":
            if qty > ZERO:
                wavg = cost / qty
                realized += abs(tx_qty) * (tx_price - wavg)
                cost += tx_qty * wavg   # tx_qty is negative for sell
                qty += tx_qty           # reduces holdings
                qty = max(ZERO, qty)
                cost = max(ZERO, cost)

        elif tx.tx_type == "buy_option":
            cost += tx_qty * tx_price * multiplier
            qty += tx_qty

        elif tx.tx_type == "sell_option":
            if qty > ZERO:
                wavg = cost / qty
                realized += abs(tx_qty) * (tx_price * multiplier - wavg / multiplier)
            cost += tx_qty * (tx_price * multiplier)
            qty += tx_qty
            qty = max(ZERO, qty)
            cost = max(ZERO, cost)

        elif tx.tx_type == "option_expire":
            # Option expires worthless: entire cost is lost P&L
            realized -= cost
            qty = ZERO
            cost = ZERO

        elif tx.tx_type == "stock_split":
            ratio = Decimal(str(tx.corporate_ratio or 1))
            qty *= ratio
            # cost stays the same; average_cost decreases proportionally

        elif tx.tx_type == "reverse_split":
            ratio = Decimal(str(tx.corporate_ratio or 1))
            if ratio > ZERO:
                qty /= ratio

    wavg = cost / qty if qty > ZERO else ZERO

    return PositionResult(
        asset_code=asset_code_upper,
        asset_type=asset_type,
        quantity=qty,
        average_cost=wavg,
        total_cost=cost,
        currency=currency or "USD",
        realized_pnl=realized,
    )


def calc_all_positions(
    account_id: int,
    as_of_date: date,
    db: Session,
) -> list[PositionResult]:
    """
    Calculate all positions for an account as of as_of_date.

    Returns only assets with non-zero quantity.
    """
    # Collect unique asset codes from both checkpoints and transactions
    codes_from_checkpoints: set[str] = {
        row[0].upper()
        for row in db.query(Position.asset_code)
        .filter(
            Position.account_id == account_id,
            Position.snapshot_date <= as_of_date,
        )
        .distinct()
        .all()
    }
    codes_from_transactions: set[str] = {
        row[0].upper()
        for row in db.query(Transaction.asset_code)
        .filter(
            Transaction.account_id == account_id,
            Transaction.tx_category == "EQUITY",
            Transaction.trade_date <= as_of_date,
            Transaction.asset_code.isnot(None),
        )
        .distinct()
        .all()
    }
    all_codes = codes_from_checkpoints | codes_from_transactions

    results = []
    for code in sorted(all_codes):
        pos = calc_position(account_id, code, as_of_date, db)
        if pos.quantity > ZERO:
            results.append(pos)

    return results


def recalculate_position(account_id: int, asset_code: str, db: Session) -> dict:
    """
    V4.2: Replay ALL TRADE transactions for (account, asset) from the beginning.

    - Writes year-end Position checkpoints to the Position table.
    - Auto-fills tx.realized_pnl on sell transactions (if not already set).
    - Returns {quantity: float, average_cost: float} for the current state.
    - Handles both legacy tx_types (buy/sell) and v4.2 types (stock_buy/stock_sell).
    """
    _BUY = {"stock_buy", "buy", "option_buy", "buy_option", "option_exercise", "rights_issue"}
    _SELL = {"stock_sell", "sell", "option_sell", "sell_option"}
    _EXPIRE = {"option_expire"}
    _SPLIT = {"stock_split", "reverse_split"}

    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.asset_code == asset_code,
            Transaction.tx_category.in_(["TRADE", "EQUITY"]),
        )
        .order_by(Transaction.trade_date, Transaction.id)
        .all()
    )

    qty = ZERO
    cost = ZERO
    checkpoints: dict[int, dict] = {}
    currency = "USD"

    for tx in txns:
        if tx.currency:
            currency = tx.currency
        tx_type = (tx.tx_type or "").lower()
        quantity = abs(Decimal(str(tx.quantity or 0)))
        price = Decimal(str(tx.price or 0))
        commission = abs(Decimal(str(tx.commission or tx.fee or 0)))

        if tx_type in _BUY:
            cost += quantity * price + commission
            qty += quantity

        elif tx_type in _SELL:
            wavg = (cost / qty) if qty > ZERO else ZERO
            realized = quantity * (price - wavg)
            if tx.realized_pnl is None:
                tx.realized_pnl = float(realized)
            cost -= quantity * wavg
            qty -= quantity
            if qty < Decimal("0.000001"):
                qty = ZERO
                cost = ZERO

        elif tx_type in _EXPIRE:
            if qty > ZERO:
                wavg = cost / qty
                cost -= quantity * wavg
            qty = max(qty - quantity, ZERO)

        elif tx_type == "stock_split":
            ratio = Decimal(str(tx.corporate_ratio or 1))
            qty = qty * ratio

        elif tx_type == "reverse_split":
            ratio = Decimal(str(tx.corporate_ratio or 1))
            if ratio > ZERO:
                qty = qty / ratio

        wavg = (cost / qty) if qty > ZERO else ZERO
        year = tx.trade_date.year
        checkpoints[year] = {
            "quantity": float(qty),
            "average_cost": float(wavg),
            "snapshot_date": date(year, 12, 31),
            "currency": currency,
        }

    db.flush()

    for cp in checkpoints.values():
        _upsert_position_v42(account_id, asset_code, cp, db)

    db.commit()

    wavg = float((cost / qty) if qty > ZERO else ZERO)
    return {"quantity": float(qty), "average_cost": wavg}


def _upsert_position_v42(account_id: int, asset_code: str, cp: dict, db: Session):
    snap = cp["snapshot_date"]
    existing = (
        db.query(Position)
        .filter(
            Position.account_id == account_id,
            Position.asset_code == asset_code,
            Position.snapshot_date == snap,
        )
        .first()
    )
    if existing:
        existing.quantity = cp["quantity"]
        existing.average_cost = cp["average_cost"]
        existing.currency = cp.get("currency", existing.currency)
    else:
        db.add(Position(
            account_id=account_id,
            asset_code=asset_code,
            quantity=cp["quantity"],
            average_cost=cp["average_cost"],
            snapshot_date=snap,
            currency=cp.get("currency", "USD"),
        ))


def recalculate_all_positions(account_id: int, db: Session) -> list[dict]:
    """Recalculate all positions for an account. Called after bulk CSV import."""
    rows = (
        db.query(Transaction.asset_code)
        .filter(
            Transaction.account_id == account_id,
            Transaction.asset_code.isnot(None),
            Transaction.tx_category.in_(["TRADE", "EQUITY"]),
        )
        .distinct()
        .all()
    )
    results = []
    for (asset_code,) in rows:
        r = recalculate_position(account_id, asset_code, db)
        r["asset_code"] = asset_code
        results.append(r)
    return results


def get_realized_pnl(
    account_id: int,
    asset_code: str,
    period_start: date,
    period_end: date,
    db: Session,
) -> Decimal:
    """
    Compute realized P&L for a specific asset within a date range.
    """
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.asset_code == asset_code.upper(),
            Transaction.tx_category == "EQUITY",
            Transaction.tx_type.in_(["sell", "sell_option", "option_expire"]),
            Transaction.trade_date >= period_start,
            Transaction.trade_date <= period_end,
        )
        .all()
    )

    # Use stored realized_pnl if available; otherwise re-derive
    total = ZERO
    for tx in txns:
        if tx.realized_pnl is not None:
            total += Decimal(str(tx.realized_pnl))
    return total
