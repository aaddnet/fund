from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import NAVRecord, ShareTransaction


def _is_quarter_month(month: int):
    return month in {3, 6, 9, 12}


def subscribe(db: Session, fund_id: int, client_id: int, tx_date, amount_usd: Decimal):
    if not _is_quarter_month(tx_date.month):
        raise ValueError("subscribe only allowed in quarter-end month")
    nav = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=tx_date).first()
    if not nav:
        raise ValueError("missing nav_at_date")
    shares = amount_usd / Decimal(str(nav.nav_per_share))
    row = ShareTransaction(fund_id=fund_id, client_id=client_id, tx_date=tx_date, tx_type="subscribe", amount_usd=amount_usd, shares=shares, nav_at_date=nav.nav_per_share)
    db.add(row)
    db.commit()
    return row


def redeem(db: Session, fund_id: int, client_id: int, tx_date, amount_usd: Decimal):
    if not _is_quarter_month(tx_date.month):
        raise ValueError("redeem only allowed in quarter-end month")
    nav = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=tx_date).first()
    if not nav:
        raise ValueError("missing nav_at_date")
    shares = amount_usd / Decimal(str(nav.nav_per_share))
    row = ShareTransaction(fund_id=fund_id, client_id=client_id, tx_date=tx_date, tx_type="redeem", amount_usd=amount_usd, shares=shares, nav_at_date=nav.nav_per_share)
    db.add(row)
    db.commit()
    return row


def history(db: Session):
    return db.query(ShareTransaction).order_by(ShareTransaction.tx_date.desc()).all()
