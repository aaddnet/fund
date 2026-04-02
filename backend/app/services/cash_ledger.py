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

    V4.2 rules (§2.3):
    - TRADE buy/sell:      net = gross_amount + commission + transaction_fee + other_fee
    - TRADE option:        premium flow via gross_amount + fees
    - TRADE option_expire: no cash
    - CASH (all sub-types):net = gross_amount + commission + transaction_fee + other_fee
    - FX fx_trade:         from_currency reduces, to_currency increases, commission in tx.currency
    - LENDING lending_income: gross_amount + fees hit cash
    - LENDING lending_out/return: no cash (collateral tracked separately)
    - ACCRUAL:             no cash
    - CORPORATE stock_split/reverse_split: no cash
    - CORPORATE rights_issue: net cash outflow

    Legacy EQUITY / MARGIN categories are also supported for backward compat.
    """
    impacts: list[CashImpact] = []
    settle = tx.settle_date or tx.trade_date

    category = (tx.tx_category or "EQUITY").upper()
    tx_type = (tx.tx_type or "").lower()

    # V4.2 net calculation helper
    def _net_v42():
        g = Decimal(str(tx.gross_amount or 0))
        c = Decimal(str(tx.commission or 0))
        t = Decimal(str(tx.transaction_fee or 0))
        o = Decimal(str(tx.other_fee or 0))
        return g + c + t + o

    # Legacy net (pre-v4.2): amount + fee
    def _net_legacy():
        a = Decimal(str(tx.amount or 0))
        f = Decimal(str(tx.fee or 0))
        return a + f

    def _net():
        """Use v4.2 fields if gross_amount is set, else fall back to legacy."""
        if tx.gross_amount is not None:
            return _net_v42()
        return _net_legacy()

    # ── TRADE (v4.2) ──────────────────────────────────────────────────────
    if category == "TRADE":
        if tx_type in ("stock_buy", "option_buy", "buy", "buy_option", "option_exercise", "rights_issue"):
            net = _net()
            if net != ZERO:
                impacts.append(CashImpact(currency=tx.currency, delta=net, settle_date=settle))

        elif tx_type in ("stock_sell", "option_sell", "sell", "sell_option"):
            net = _net()
            if net != ZERO:
                impacts.append(CashImpact(currency=tx.currency, delta=net, settle_date=settle))

        # option_expire, stock_split, reverse_split: no direct cash

    # ── EQUITY (legacy) ───────────────────────────────────────────────────
    elif category == "EQUITY":
        fee = Decimal(str(tx.fee or 0))
        if tx_type in ("buy", "stock_buy"):
            qty = abs(Decimal(str(tx.quantity or 0)))
            price = Decimal(str(tx.price or 0))
            delta = -(qty * price) + fee  # outflow
            impacts.append(CashImpact(currency=tx.currency, delta=delta, settle_date=settle))

        elif tx_type in ("sell", "stock_sell"):
            qty = abs(Decimal(str(tx.quantity or 0)))
            price = Decimal(str(tx.price or 0))
            delta = qty * price + fee  # inflow
            impacts.append(CashImpact(currency=tx.currency, delta=delta, settle_date=settle))

        elif tx_type in ("buy_option", "option_buy"):
            qty = abs(Decimal(str(tx.quantity or 0)))
            price = Decimal(str(tx.price or 0))
            multiplier = Decimal(str(tx.option_multiplier or 100))
            delta = -(qty * price * multiplier) + fee
            impacts.append(CashImpact(currency=tx.currency, delta=delta, settle_date=settle))

        elif tx_type in ("sell_option", "option_sell"):
            qty = abs(Decimal(str(tx.quantity or 0)))
            price = Decimal(str(tx.price or 0))
            multiplier = Decimal(str(tx.option_multiplier or 100))
            delta = qty * price * multiplier + fee
            impacts.append(CashImpact(currency=tx.currency, delta=delta, settle_date=settle))

    # ── CASH ──────────────────────────────────────────────────────────────
    elif category in ("CASH", "MARGIN"):
        # Covers: deposit_eft, deposit_transfer, withdrawal, dividend, pil,
        #         dividend_fee, interest_debit, interest_credit, adr_fee,
        #         other_fee, adjustment, lending_income
        net = _net()
        if net != ZERO:
            impacts.append(CashImpact(currency=tx.currency, delta=net, settle_date=settle))

    # ── FX ────────────────────────────────────────────────────────────────
    elif category == "FX":
        if tx_type in ("fx_trade", "fx"):
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
            comm = Decimal(str(tx.commission or tx.fee or 0))
            if comm != ZERO:
                impacts.append(CashImpact(
                    currency=tx.currency,
                    delta=comm,
                    settle_date=settle,
                ))
        # fx_translation: P&L adjustment — no cash

    # ── LENDING ───────────────────────────────────────────────────────────
    elif category in ("LENDING", "SECURITIES_LENDING"):
        if tx_type == "lending_income":
            net = _net()
            if net != ZERO:
                impacts.append(CashImpact(currency=tx.currency, delta=net, settle_date=settle))
        # lending_out / lending_return: no cash flow

    # ── ACCRUAL ───────────────────────────────────────────────────────────
    elif category == "ACCRUAL":
        pass  # affects NAV but not cash

    # ── CORPORATE ─────────────────────────────────────────────────────────
    elif category == "CORPORATE":
        if tx_type == "rights_issue":
            net = _net()
            if net != ZERO:
                impacts.append(CashImpact(currency=tx.currency, delta=net, settle_date=settle))
        # stock_split, reverse_split, spinoff, merger: no direct cash

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
