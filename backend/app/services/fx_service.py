"""fx_service.py

V4: FX trade recording, P&L calculation, and summary helpers.

Usage:
    from app.services.fx_service import record_fx_trade, calc_fx_pnl, get_fx_summary
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, getcontext
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ExchangeRate, Transaction

getcontext().prec = 28
logger = logging.getLogger(__name__)

ZERO = Decimal("0")


@dataclass
class FXSummary:
    from_currency: str
    to_currency: str
    total_from: Decimal      # total amount sold (positive)
    total_to: Decimal        # total amount bought (positive)
    avg_rate: Decimal        # average rate = total_to / total_from
    total_fee_usd: Decimal
    realized_pnl_usd: Decimal   # mark-to-market P&L vs current rate


def record_fx_trade(
    account_id: int,
    trade_date: date,
    from_currency: str,
    from_amount: Decimal,   # positive; stored as negative fx_from_amount
    to_currency: str,
    to_amount: Decimal,     # positive; stored as positive fx_to_amount
    fee: Decimal = ZERO,
    fee_currency: Optional[str] = None,
    description: Optional[str] = None,
    source: str = "manual",
    import_batch_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Transaction:
    """
    Create a Transaction record for an FX trade.

    One FX transaction = one DB row that captures both sides of the trade.
    """
    rate = to_amount / from_amount if from_amount > ZERO else ZERO

    tx = Transaction(
        account_id=account_id,
        tx_category="FX",
        tx_type="fx_trade",
        source=source,
        trade_date=trade_date,
        currency=fee_currency or from_currency,
        amount=ZERO,
        fee=-abs(fee),  # fee is always negative
        description=description or f"{from_currency}.{to_currency} Forex Trade {trade_date}",
        fx_from_currency=from_currency.upper(),
        fx_from_amount=-abs(from_amount),   # negative = sold / outflow
        fx_to_currency=to_currency.upper(),
        fx_to_amount=abs(to_amount),        # positive = bought / inflow
        fx_rate=rate,
        import_batch_id=import_batch_id,
    )
    if db is not None:
        db.add(tx)
        db.flush()
    return tx


def calc_fx_pnl(
    account_id: int,
    period_start: date,
    period_end: date,
    db: Session,
    as_of_date: Optional[date] = None,
) -> Decimal:
    """
    Calculate unrealized/mark-to-market FX P&L.

    For each FX trade in the period:
      USD paid out = |fx_from_amount| (assuming from = USD)
      USD equivalent at current rate = fx_to_amount × current(to/USD rate)
      pnl = usd_equivalent - usd_paid

    If from_currency != USD, the logic reverses appropriately.
    """
    eval_date = as_of_date or period_end

    fx_txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.tx_category == "FX",
            Transaction.tx_type == "fx_trade",
            Transaction.trade_date >= period_start,
            Transaction.trade_date <= period_end,
        )
        .all()
    )

    total_pnl = ZERO
    for tx in fx_txns:
        if not tx.fx_from_currency or not tx.fx_to_currency:
            continue

        from_ccy = tx.fx_from_currency.upper()
        to_ccy = tx.fx_to_currency.upper()
        from_amt = abs(Decimal(str(tx.fx_from_amount or 0)))
        to_amt = abs(Decimal(str(tx.fx_to_amount or 0)))

        # Resolve current USD values
        from_rate = _get_rate_to_usd(from_ccy, eval_date, db)
        to_rate = _get_rate_to_usd(to_ccy, eval_date, db)

        if from_rate is None or to_rate is None:
            logger.warning("FX P&L: missing rate for %s or %s on %s", from_ccy, to_ccy, eval_date)
            continue

        usd_sold = from_amt * from_rate
        usd_bought = to_amt * to_rate
        pnl = usd_bought - usd_sold
        total_pnl += pnl

    return total_pnl


def get_fx_summary(
    account_id: int,
    db: Session,
    as_of_date: Optional[date] = None,
) -> list[FXSummary]:
    """
    Summarize all FX trades for the account, grouped by currency pair.
    Includes mark-to-market P&L at as_of_date (defaults to today).
    """
    from datetime import date as _date
    eval_date = as_of_date or _date.today()

    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.tx_category == "FX",
            Transaction.tx_type == "fx_trade",
        )
        .all()
    )

    # Group by (from_currency, to_currency)
    buckets: dict[tuple[str, str], dict] = {}
    for tx in txns:
        if not tx.fx_from_currency or not tx.fx_to_currency:
            continue
        key = (tx.fx_from_currency.upper(), tx.fx_to_currency.upper())
        if key not in buckets:
            buckets[key] = {
                "total_from": ZERO,
                "total_to": ZERO,
                "total_fee": ZERO,
            }
        buckets[key]["total_from"] += abs(Decimal(str(tx.fx_from_amount or 0)))
        buckets[key]["total_to"] += abs(Decimal(str(tx.fx_to_amount or 0)))
        buckets[key]["total_fee"] += abs(Decimal(str(tx.fee or 0)))

    summaries = []
    for (from_ccy, to_ccy), data in sorted(buckets.items()):
        total_from = data["total_from"]
        total_to = data["total_to"]
        avg_rate = total_to / total_from if total_from > ZERO else ZERO

        # Mark-to-market P&L
        from_rate = _get_rate_to_usd(from_ccy, eval_date, db)
        to_rate = _get_rate_to_usd(to_ccy, eval_date, db)
        if from_rate and to_rate:
            usd_sold = total_from * from_rate
            usd_bought = total_to * to_rate
            pnl = usd_bought - usd_sold
        else:
            pnl = ZERO

        # Fees in USD
        fee_rate = _get_rate_to_usd(from_ccy, eval_date, db)
        fee_usd = data["total_fee"] * (fee_rate or ZERO)

        summaries.append(FXSummary(
            from_currency=from_ccy,
            to_currency=to_ccy,
            total_from=total_from,
            total_to=total_to,
            avg_rate=avg_rate,
            total_fee_usd=fee_usd,
            realized_pnl_usd=pnl,
        ))

    return summaries


def _get_rate_to_usd(
    currency: str,
    as_of_date: date,
    db: Session,
) -> Optional[Decimal]:
    """Look up latest FX rate to USD on or before as_of_date."""
    if currency.upper() == "USD":
        return Decimal("1")

    row = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.base_currency == currency.upper(),
            ExchangeRate.quote_currency == "USD",
            ExchangeRate.snapshot_date <= as_of_date,
        )
        .order_by(ExchangeRate.snapshot_date.desc())
        .first()
    )
    if row:
        return Decimal(str(row.rate))

    # Try inverse
    row = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.base_currency == "USD",
            ExchangeRate.quote_currency == currency.upper(),
            ExchangeRate.snapshot_date <= as_of_date,
        )
        .order_by(ExchangeRate.snapshot_date.desc())
        .first()
    )
    if row:
        rate = Decimal(str(row.rate))
        return Decimal("1") / rate if rate > ZERO else None

    return None
