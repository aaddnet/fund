from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Client, Fund, NAVRecord, ShareTransaction

ZERO = Decimal("0")


def _is_quarter_month(month: int):
    return month in {3, 6, 9, 12}


def _require_positive_amount(amount_usd: Decimal) -> Decimal:
    amount = Decimal(str(amount_usd))
    if amount <= ZERO:
        raise ValueError("amount_usd must be greater than 0")
    return amount


def _require_locked_nav(db: Session, fund_id: int, tx_date):
    nav = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=tx_date).first()
    if not nav:
        raise ValueError("missing nav_at_date")
    if not nav.is_locked:
        raise ValueError("share transaction requires a locked nav record")
    nav_per_share = Decimal(str(nav.nav_per_share or 0))
    if nav_per_share <= ZERO:
        raise ValueError("nav_at_date must be greater than 0")
    return nav


def _require_fund(db: Session, fund_id: int) -> Fund:
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise ValueError("fund not found")
    return fund


def _require_client(db: Session, client_id: int) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("client not found")
    return client


def _share_delta_case():
    # redeem 在账本里存正数 shares，通过符号映射统一做净额聚合，查询会更稳定。
    return case((ShareTransaction.tx_type == "redeem", -ShareTransaction.shares), else_=ShareTransaction.shares)


def get_client_fund_balance(db: Session, fund_id: int, client_id: int) -> Decimal:
    balance = (
        db.query(func.coalesce(func.sum(_share_delta_case()), 0))
        .filter(ShareTransaction.fund_id == fund_id, ShareTransaction.client_id == client_id)
        .scalar()
    )
    return Decimal(str(balance or 0))


def get_fund_balance(db: Session, fund_id: int) -> Decimal:
    balance = db.query(func.coalesce(func.sum(_share_delta_case()), 0)).filter(ShareTransaction.fund_id == fund_id).scalar()
    return Decimal(str(balance or 0))


def sync_fund_total_shares(db: Session, fund: Fund) -> Decimal:
    derived_total = get_fund_balance(db, fund.id)
    # 账本是份额单一事实源，fund.total_shares 作为读优化字段，需要每次回写保持同步。
    fund.total_shares = derived_total
    db.flush()
    return derived_total


def _serialize_share_transaction(row: ShareTransaction) -> dict:
    return {
        "id": row.id,
        "fund_id": row.fund_id,
        "client_id": row.client_id,
        "tx_date": row.tx_date.isoformat(),
        "tx_type": row.tx_type,
        "amount_usd": float(Decimal(str(row.amount_usd))),
        "shares": float(Decimal(str(row.shares))),
        "nav_at_date": float(Decimal(str(row.nav_at_date))),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_balance(fund_id: int, client_id: int, share_balance: Decimal) -> dict:
    return {
        "fund_id": fund_id,
        "client_id": client_id,
        "share_balance": float(share_balance),
    }


def subscribe(db: Session, fund_id: int, client_id: int, tx_date, amount_usd: Decimal):
    if not _is_quarter_month(tx_date.month):
        raise ValueError("subscribe only allowed in quarter-end month")

    amount = _require_positive_amount(amount_usd)
    nav = _require_locked_nav(db, fund_id, tx_date)
    fund = _require_fund(db, fund_id)
    _require_client(db, client_id)

    shares = amount / Decimal(str(nav.nav_per_share))
    row = ShareTransaction(
        fund_id=fund_id,
        client_id=client_id,
        tx_date=tx_date,
        tx_type="subscribe",
        amount_usd=amount,
        shares=shares,
        nav_at_date=nav.nav_per_share,
    )
    db.add(row)
    db.flush()
    sync_fund_total_shares(db, fund)
    db.commit()
    db.refresh(row)
    return _serialize_share_transaction(row)


def redeem(db: Session, fund_id: int, client_id: int, tx_date, amount_usd: Decimal):
    if not _is_quarter_month(tx_date.month):
        raise ValueError("redeem only allowed in quarter-end month")

    amount = _require_positive_amount(amount_usd)
    nav = _require_locked_nav(db, fund_id, tx_date)
    fund = _require_fund(db, fund_id)
    _require_client(db, client_id)

    shares = amount / Decimal(str(nav.nav_per_share))
    client_balance = get_client_fund_balance(db, fund_id, client_id)
    if shares > client_balance:
        raise ValueError("redeem shares exceed client share balance")

    fund_balance = get_fund_balance(db, fund_id)
    if shares > fund_balance:
        raise ValueError("redeem shares exceed fund total shares")

    row = ShareTransaction(
        fund_id=fund_id,
        client_id=client_id,
        tx_date=tx_date,
        tx_type="redeem",
        amount_usd=amount,
        shares=shares,
        nav_at_date=nav.nav_per_share,
    )
    db.add(row)
    db.flush()
    sync_fund_total_shares(db, fund)
    db.commit()
    db.refresh(row)
    return _serialize_share_transaction(row)


def history(
    db: Session,
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    date_from=None,
    date_to=None,
):
    query = db.query(ShareTransaction)
    if fund_id is not None:
        query = query.filter(ShareTransaction.fund_id == fund_id)
    if client_id is not None:
        query = query.filter(ShareTransaction.client_id == client_id)
    if tx_type:
        query = query.filter(ShareTransaction.tx_type == tx_type)
    if date_from is not None:
        query = query.filter(ShareTransaction.tx_date >= date_from)
    if date_to is not None:
        query = query.filter(ShareTransaction.tx_date <= date_to)
    return [_serialize_share_transaction(row) for row in query.order_by(ShareTransaction.tx_date.desc(), ShareTransaction.id.desc()).all()]


def balances(db: Session, fund_id: Optional[int] = None, client_id: Optional[int] = None):
    query = db.query(
        ShareTransaction.fund_id,
        ShareTransaction.client_id,
        func.coalesce(func.sum(_share_delta_case()), 0).label("share_balance"),
    )
    if fund_id is not None:
        query = query.filter(ShareTransaction.fund_id == fund_id)
    if client_id is not None:
        query = query.filter(ShareTransaction.client_id == client_id)

    rows = (
        query.group_by(ShareTransaction.fund_id, ShareTransaction.client_id)
        .order_by(ShareTransaction.fund_id.asc(), ShareTransaction.client_id.asc())
        .all()
    )
    return [_serialize_balance(row.fund_id, row.client_id, Decimal(str(row.share_balance or 0))) for row in rows]
