from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal, getcontext
from typing import Any, Optional

# Explicit precision context for NAV calculations involving large position quantities.
getcontext().prec = 28

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import Account, AssetPrice, AssetSnapshot, CashPosition, ExchangeRate, Fund, NAVRecord, Position

USD = "USD"
ZERO = Decimal("0")


def calc_nav(db: Session, fund_id: int, nav_date, force: bool = False):
    existing = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=nav_date).first()
    if existing and not force:
        return existing
    if existing and force:
        # Delete stale record and its asset snapshots before recalculating
        db.query(AssetSnapshot).filter(AssetSnapshot.nav_record_id == existing.id).delete()
        db.delete(existing)
        db.flush()

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise ValueError(f"Fund {fund_id} was not found.")

    account_ids = [row[0] for row in db.query(Account.id).filter(Account.fund_id == fund_id).all()]
    if not account_ids:
        raise ValueError(f"Fund {fund_id} has no accounts.")

    # For each (account, asset), take the latest snapshot on or before nav_date.
    # This ensures we always use the most recent known position even when there
    # is no snapshot exactly on nav_date (e.g. a quarterly NAV date).
    latest_subq = (
        db.query(
            Position.account_id,
            Position.asset_code,
            func.max(Position.snapshot_date).label("max_date"),
        )
        .filter(
            Position.account_id.in_(account_ids),
            Position.snapshot_date <= nav_date,
        )
        .group_by(Position.account_id, Position.asset_code)
        .subquery()
    )
    positions = (
        db.query(Position)
        .join(
            latest_subq,
            and_(
                Position.account_id == latest_subq.c.account_id,
                Position.asset_code == latest_subq.c.asset_code,
                Position.snapshot_date == latest_subq.c.max_date,
            ),
        )
        .order_by(Position.account_id.asc(), Position.asset_code.asc())
        .all()
    )
    if not positions:
        # No positions on this date (e.g. historical date before fund had positions).
        # Return a $0 NAV record instead of raising an error.
        total_shares_zero = Decimal(str(fund.total_shares or 1))
        nav_zero = NAVRecord(
            fund_id=fund_id,
            nav_date=nav_date,
            total_assets_usd=ZERO,
            total_shares=total_shares_zero,
            nav_per_share=ZERO,
            is_locked=True,
        )
        db.add(nav_zero)
        db.commit()
        db.refresh(nav_zero)
        return nav_zero

    price_map = {
        row.asset_code.upper(): row
        for row in db.query(AssetPrice).filter(AssetPrice.snapshot_date == nav_date).all()
    }
    rate_map = _build_rate_map(db, nav_date)

    total_assets_usd = ZERO
    grouped_snapshots: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "quantity": ZERO,
            "value_usd": ZERO,
            "value_native": ZERO,
            "price_native": ZERO,
            "price_usd": ZERO,
            "fx_rate_to_usd": Decimal("1"),
            "accounts": set(),
        }
    )

    for position in positions:
        valuation = _value_position(position, price_map, rate_map)
        total_assets_usd += valuation["value_usd"]

        # 注意这里按 asset + currency 聚合快照，方便 V1 页面快速看持仓结构，
        # 同时保留 account_ids 便于排查某个资产来自哪些账户。
        bucket_key = (position.asset_code.upper(), position.currency.upper())
        bucket = grouped_snapshots[bucket_key]
        bucket["quantity"] += Decimal(str(position.quantity))
        bucket["value_usd"] += valuation["value_usd"]
        bucket["value_native"] += valuation["value_native"]
        bucket["accounts"].add(position.account_id)
        if bucket["quantity"] != ZERO:
            bucket["price_native"] = bucket["value_native"] / bucket["quantity"]
            bucket["price_usd"] = bucket["value_usd"] / bucket["quantity"]
        bucket["fx_rate_to_usd"] = valuation["fx_rate_to_usd"]

    # Include cash positions: latest snapshot per (account, currency) on or before nav_date
    cash_subq = (
        db.query(
            CashPosition.account_id,
            CashPosition.currency,
            func.max(CashPosition.snapshot_date).label("max_date"),
        )
        .filter(
            CashPosition.account_id.in_(account_ids),
            CashPosition.snapshot_date <= nav_date,
        )
        .group_by(CashPosition.account_id, CashPosition.currency)
        .subquery()
    )
    cash_rows = (
        db.query(CashPosition)
        .join(
            cash_subq,
            and_(
                CashPosition.account_id == cash_subq.c.account_id,
                CashPosition.currency == cash_subq.c.currency,
                CashPosition.snapshot_date == cash_subq.c.max_date,
            ),
        )
        .all()
    )
    cash_total = ZERO
    for cr in cash_rows:
        cash_total += _resolve_rate_to_usd(cr.currency.upper(), rate_map) * Decimal(str(cr.amount))
    positions_total = total_assets_usd
    total_assets_usd += cash_total

    total_shares = Decimal(str(fund.total_shares or 0))
    if total_shares <= ZERO:
        # V1 允许先算出总资产，再由后续 share 流程逐步补齐份额。
        total_shares = Decimal("1")
    nav_per_share = total_assets_usd / total_shares if total_shares else ZERO

    nav = NAVRecord(
        fund_id=fund_id,
        nav_date=nav_date,
        total_assets_usd=total_assets_usd,
        total_shares=total_shares,
        nav_per_share=nav_per_share,
        is_locked=True,
        cash_total_usd=cash_total,
        positions_total_usd=positions_total,
    )
    db.add(nav)
    db.flush()

    for (asset_code, currency), snapshot in grouped_snapshots.items():
        db.add(
            AssetSnapshot(
                nav_record_id=nav.id,
                asset_code=asset_code,
                quantity=snapshot["quantity"],
                price_usd=snapshot["price_usd"],
                value_usd=snapshot["value_usd"],
                currency=currency,
                price_native=snapshot["price_native"],
                value_native=snapshot["value_native"],
                fx_rate_to_usd=snapshot["fx_rate_to_usd"],
                account_ids=",".join(str(account_id) for account_id in sorted(snapshot["accounts"])),
            )
        )

    db.commit()
    db.refresh(nav)
    return nav


def rebuild_nav_batch(db: Session, fund_id: int, start_date: date, end_date: date, frequency: str = "quarterly", force: bool = False) -> list[dict]:
    """
    Batch-rebuild NAV records for a date range at a given frequency.
    Returns a list of {date, nav_per_share, status} result dicts.
    """
    dates = _generate_nav_dates(start_date, end_date, frequency)
    results = []
    for d in dates:
        try:
            nav = calc_nav(db, fund_id, d, force=force)
            results.append({
                "date": d.isoformat(),
                "nav_per_share": float(nav.nav_per_share),
                "total_assets_usd": float(nav.total_assets_usd),
                "status": "ok",
            })
        except Exception as exc:
            results.append({"date": d.isoformat(), "status": "error", "msg": str(exc)})
    return results


def _generate_nav_dates(start: date, end: date, frequency: str) -> list[date]:
    """Generate NAV calculation dates for the given frequency."""
    dates: list[date] = []
    if frequency == "quarterly":
        for year in range(start.year, end.year + 1):
            for month in [3, 6, 9, 12]:
                last_day = calendar.monthrange(year, month)[1]
                d = date(year, month, last_day)
                if start <= d <= end:
                    dates.append(d)
    elif frequency == "yearly":
        for year in range(start.year, end.year + 1):
            d = date(year, 12, 31)
            if start <= d <= end:
                dates.append(d)
    elif frequency == "monthly":
        year, month = start.year, start.month
        while True:
            last_day = calendar.monthrange(year, month)[1]
            d = date(year, month, last_day)
            if d > end:
                break
            if d >= start:
                dates.append(d)
            month += 1
            if month > 12:
                month = 1
                year += 1
    return sorted(dates)


def list_nav(db: Session, fund_id: Optional[int] = None):
    query = db.query(NAVRecord)
    if fund_id is not None:
        query = query.filter(NAVRecord.fund_id == fund_id)
    return query.order_by(NAVRecord.nav_date.desc(), NAVRecord.id.desc()).all()


def _value_position(position: Position, price_map: dict[str, AssetPrice], rate_map: dict[tuple[str, str], Decimal]) -> dict[str, Decimal]:
    asset_code = position.asset_code.upper()
    currency = position.currency.upper()
    quantity = Decimal(str(position.quantity))
    average_cost = Decimal(str(position.average_cost or 0))
    price_row = price_map.get(asset_code)

    fx_rate_to_usd = _resolve_rate_to_usd(currency, rate_map)
    if price_row is not None:
        price_usd = Decimal(str(price_row.price_usd))
        value_usd = quantity * price_usd
        price_native = price_usd if currency == USD else (price_usd / fx_rate_to_usd if fx_rate_to_usd else ZERO)
        value_native = quantity * price_native
    else:
        # 没有价格快照时，V1 使用持仓平均成本作为兜底估值，
        # 非 USD 资产再通过对应 snapshot_date 的汇率折算到 USD。
        price_native = average_cost
        value_native = quantity * price_native
        price_usd = price_native if currency == USD else price_native * fx_rate_to_usd
        value_usd = value_native if currency == USD else value_native * fx_rate_to_usd

    return {
        "price_native": price_native,
        "value_native": value_native,
        "price_usd": price_usd,
        "value_usd": value_usd,
        "fx_rate_to_usd": fx_rate_to_usd,
    }


def _build_rate_map(db: Session, snapshot_date) -> dict[tuple[str, str], Decimal]:
    return {
        (row.base_currency.upper(), row.quote_currency.upper()): Decimal(str(row.rate))
        for row in db.query(ExchangeRate).filter(ExchangeRate.snapshot_date == snapshot_date).all()
    }


def _resolve_rate_to_usd(currency: str, rate_map: dict[tuple[str, str], Decimal]) -> Decimal:
    if currency == USD:
        return Decimal("1")

    direct = rate_map.get((currency, USD))
    if direct is not None:
        return direct

    inverse = rate_map.get((USD, currency))
    if inverse:
        return Decimal("1") / inverse

    raise ValueError(f"Missing FX rate for {currency}/USD on NAV snapshot date.")
