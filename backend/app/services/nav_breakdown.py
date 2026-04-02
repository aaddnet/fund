"""nav_breakdown.py

V4.1: Compute full NAV breakdown for an IB multi-currency margin account.

NAV = Stock Value (cost basis) + Cash (by currency, can be negative) +
      Accruals (net unreversed) + Securities Lending (net = 0)

Note: Stock value uses cost basis (average_cost × quantity) as an estimate
when no real-time price feed is available.  Securities lending net = 0
because Cash Collateral (asset) and Securities Lent (liability) offset.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Transaction
from app.models.entities import Accrual, CashCollateral
from app.services.cash_ledger import get_all_cash_balances
from app.services.position_calculator import calc_all_positions

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


def get_nav_breakdown(account_id: int, as_of_date: date, db: Session) -> dict:
    """
    Return full NAV breakdown dict for an account as of as_of_date.

    Structure:
    {
      account_id, as_of_date,
      stock_value: { positions: [...], total_cost_usd: float },
      cash: { balances: {USD: float, HKD: float, ...}, total_usd: float },
      accruals: { items: [...], total_usd: float },
      securities_lending: { positions: [...], net_usd: 0, income_ytd: float },
      total_nav_usd: float
    }
    """
    # ── 1. Stock holdings (cost basis as estimate) ────────────────────────────
    positions = calc_all_positions(account_id, as_of_date, db)
    stock_positions_out = []
    total_cost_usd = ZERO
    for p in positions:
        est_value = p.quantity * p.average_cost
        total_cost_usd += est_value
        stock_positions_out.append({
            "asset_code": p.asset_code,
            "asset_type": p.asset_type,
            "quantity": float(p.quantity),
            "currency": p.currency,
            "average_cost": float(p.average_cost),
            "estimated_value": float(est_value),
            "estimated_value_usd": float(est_value),  # simplified: assume same as USD
        })

    # ── 2. Cash balances (can be negative for margin financing) ───────────────
    cash_balances = get_all_cash_balances(account_id, as_of_date, db)
    cash_balances_out = {k: float(v) for k, v in cash_balances.items()}
    # Simplified NAV: sum all balances (works well when account is primarily USD)
    # A proper multi-currency NAV would apply FX rates here.
    total_cash_usd = float(sum(cash_balances.values()))

    # ── 3. Accruals (affect NAV but not cash) ─────────────────────────────────
    accrual_rows = (
        db.query(Accrual)
        .filter(
            Accrual.account_id == account_id,
            Accrual.accrual_date <= as_of_date,
            Accrual.is_reversed.is_(False),
        )
        .order_by(Accrual.accrual_date)
        .all()
    )
    accrual_items_out = []
    total_accrual_usd = ZERO
    for a in accrual_rows:
        accrual_items_out.append({
            "id": a.id,
            "accrual_type": a.accrual_type,
            "currency": a.currency,
            "amount": float(a.amount),
            "accrual_date": a.accrual_date.isoformat(),
            "expected_pay_date": a.expected_pay_date.isoformat() if a.expected_pay_date else None,
            "asset_code": a.asset_code,
            "is_reversed": a.is_reversed,
        })
        total_accrual_usd += Decimal(str(a.amount))

    # ── 4. Securities lending positions ───────────────────────────────────────
    lending_rows = (
        db.query(CashCollateral)
        .filter(
            CashCollateral.account_id == account_id,
            CashCollateral.start_date <= as_of_date,
        )
        .filter(
            (CashCollateral.end_date.is_(None)) | (CashCollateral.end_date >= as_of_date)
        )
        .all()
    )
    lending_positions_out = []
    for lp in lending_rows:
        lending_positions_out.append({
            "id": lp.id,
            "asset_code": lp.asset_code,
            "quantity_lent": float(lp.quantity_lent),
            "collateral_usd": float(lp.collateral_usd) if lp.collateral_usd else None,
            "lending_rate": float(lp.lending_rate) if lp.lending_rate else None,
            "start_date": lp.start_date.isoformat(),
            "end_date": lp.end_date.isoformat() if lp.end_date else None,
        })

    # YTD lending income
    income_ytd_rows = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.tx_category == "SECURITIES_LENDING",
            Transaction.tx_type == "lending_income",
            Transaction.trade_date >= date(as_of_date.year, 1, 1),
            Transaction.trade_date <= as_of_date,
        )
        .all()
    )
    income_ytd = float(sum(
        Decimal(str(r.amount or 0)) + Decimal(str(r.fee or 0))
        for r in income_ytd_rows
    ))

    # ── 5. Total NAV ──────────────────────────────────────────────────────────
    total_nav_usd = float(total_cost_usd) + total_cash_usd + float(total_accrual_usd)

    return {
        "account_id": account_id,
        "as_of_date": as_of_date.isoformat(),
        "stock_value": {
            "positions": stock_positions_out,
            "total_cost_usd": float(total_cost_usd),
        },
        "cash": {
            "balances": cash_balances_out,
            "total_usd": total_cash_usd,
        },
        "accruals": {
            "items": accrual_items_out,
            "total_usd": float(total_accrual_usd),
        },
        "securities_lending": {
            "positions": lending_positions_out,
            "net_usd": 0,
            "income_ytd": income_ytd,
        },
        "total_nav_usd": total_nav_usd,
    }
