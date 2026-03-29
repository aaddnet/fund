from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, getcontext
from typing import Any, Optional

# Explicit precision context for NAV calculations involving large position quantities.
getcontext().prec = 28

from sqlalchemy.orm import Session

from app.models import Account, AssetPrice, AssetSnapshot, ExchangeRate, Fund, NAVRecord, Position

USD = "USD"
ZERO = Decimal("0")


def calc_nav(db: Session, fund_id: int, nav_date):
    existing = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=nav_date).first()
    if existing:
        return existing

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise ValueError(f"Fund {fund_id} was not found.")

    account_ids = [row[0] for row in db.query(Account.id).filter(Account.fund_id == fund_id).all()]
    if not account_ids:
        raise ValueError(f"Fund {fund_id} has no accounts.")

    positions = (
        db.query(Position)
        .filter(Position.snapshot_date == nav_date, Position.account_id.in_(account_ids))
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
