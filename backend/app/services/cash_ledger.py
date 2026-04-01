"""cash_ledger.py

V4: Compute cash balances entirely from Transaction events.
Cash balances can be negative (margin/financing liability) — this is expected
and should be included in NAV calculation as a liability.

Usage:
    from app.services.cash_ledger import get_cash_balance, get_all_cash_balances
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, getcontext
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Transaction

getcontext().prec = 28
logger = logging.getLogger(__name__)

ZERO = Decimal("0")


@dataclass
class CashImpact:
    currency: str
    delta: Decimal      # positive = inflow, negative = outflow
    settle_date: date


@dataclass
class CashEvent:
    """One line item in the cash history ledger."""
    tx_id: int
    trade_date: date
    settle_date: date
    tx_category: str
    tx_type: str
    description: Optional[str]
    currency: str
    delta: Decimal
    balance_after: Decimal   # running balance after this event


def get_cash_impacts(tx: Transaction) -> list[CashImpact]:
    """
    Given a Transaction, return list of CashImpact entries (one per affected currency).

    Rules:
    - EQUITY buy/sell:   cash decreases/increases by quantity × price + fee
    - EQUITY option:     premium flow + fee
    - CASH (all):        net_amount (amount + fee) in the transaction currency
    - FX fx_trade:       from_currency decreases, to_currency increases, fee in main currency
    - MARGIN:            same as CASH
    - CORPORATE:         no direct cash impact (unless rights_issue etc.)
    """
    impacts: list[CashImpact] = []
    settle = tx.settle_date or tx.trade_date

    category = (tx.tx_category or "EQUITY").upper()
    tx_type = (tx.tx_type or "").lower()
    fee = Decimal(str(tx.fee or 0))

    if category == "EQUITY":
        if tx_type in ("buy", "sell"):
            qty = Decimal(str(tx.quantity or 0))
            price = Decimal(str(tx.price or 0))
            # buy: cash out (negative), sell: cash in (positive)
            direction = Decimal("-1") if tx_type == "buy" else Decimal("1")
            cash_delta = direction * abs(qty) * price + fee
            impacts.append(CashImpact(
                currency=tx.currency,
                delta=cash_delta,
                settle_date=settle,
            ))

        elif tx_type in ("buy_option", "sell_option"):
            qty = Decimal(str(tx.quantity or 0))
            price = Decimal(str(tx.price or 0))
            multiplier = Decimal(str(tx.option_multiplier or 100))
            premium = abs(qty) * price * multiplier
            # buy_option: pay premium; sell_option: receive premium
            direction = Decimal("-1") if tx_type == "buy_option" else Decimal("1")
            cash_delta = direction * premium + fee
            impacts.append(CashImpact(
                currency=tx.currency,
                delta=cash_delta,
                settle_date=settle,
            ))

        # option_expire, option_exercise, stock_split, etc. → no direct cash flow
        # (option_exercise creates a new buy/sell transaction for the underlying)

    elif category in ("CASH", "MARGIN"):
        # amount = gross flow, fee is already negative
        amount = Decimal(str(tx.amount or 0))
        net = amount + fee
        if net != ZERO:
            impacts.append(CashImpact(
                currency=tx.currency,
                delta=net,
                settle_date=settle,
            ))

    elif category == "FX":
        if tx_type == "fx_trade":
            if tx.fx_from_currency and tx.fx_from_amount is not None:
                impacts.append(CashImpact(
                    currency=tx.fx_from_currency,
                    delta=Decimal(str(tx.fx_from_amount)),  # already negative
                    settle_date=settle,
                ))
            if tx.fx_to_currency and tx.fx_to_amount is not None:
                impacts.append(CashImpact(
                    currency=tx.fx_to_currency,
                    delta=Decimal(str(tx.fx_to_amount)),    # already positive
                    settle_date=settle,
                ))
            # Fee in main (from) currency
            if fee != ZERO:
                impacts.append(CashImpact(
                    currency=tx.currency,
                    delta=fee,
                    settle_date=settle,
                ))

    return impacts


def get_cash_balance(
    account_id: int,
    currency: str,
    as_of_date: date,
    db: Session,
) -> Decimal:
    """
    Compute cash balance for a specific currency as of as_of_date.
    Negative balance = financing liability (normal for margin accounts).
    """
    currency_upper = currency.upper()
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.trade_date <= as_of_date,
        )
        .order_by(Transaction.trade_date, Transaction.id)
        .all()
    )

    balance = ZERO
    for tx in txns:
        for impact in get_cash_impacts(tx):
            if impact.currency.upper() == currency_upper:
                eff_date = impact.settle_date or tx.trade_date
                if eff_date <= as_of_date:
                    balance += impact.delta

    return balance


def get_all_cash_balances(
    account_id: int,
    as_of_date: date,
    db: Session,
) -> dict[str, Decimal]:
    """
    Return all currency balances for account as of date.
    Keys are uppercase currency codes.  Values can be negative.
    """
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.trade_date <= as_of_date,
        )
        .all()
    )

    balances: dict[str, Decimal] = defaultdict(Decimal)
    for tx in txns:
        for impact in get_cash_impacts(tx):
            eff_date = impact.settle_date or tx.trade_date
            if eff_date <= as_of_date:
                balances[impact.currency.upper()] += impact.delta

    return dict(balances)


def get_cash_history(
    account_id: int,
    currency: str,
    db: Session,
    limit: int = 500,
) -> list[CashEvent]:
    """
    Return chronological cash ledger entries for a single currency,
    with running balance after each event.
    """
    currency_upper = currency.upper()
    txns = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .order_by(Transaction.trade_date, Transaction.id)
        .all()
    )

    events: list[CashEvent] = []
    running = ZERO

    for tx in txns:
        for impact in get_cash_impacts(tx):
            if impact.currency.upper() != currency_upper:
                continue
            running += impact.delta
            events.append(CashEvent(
                tx_id=tx.id,
                trade_date=tx.trade_date,
                settle_date=impact.settle_date,
                tx_category=tx.tx_category or "EQUITY",
                tx_type=tx.tx_type,
                description=tx.description,
                currency=impact.currency,
                delta=impact.delta,
                balance_after=running,
            ))

    # Return latest first (most useful for UI)
    events.reverse()
    return events[:limit]
