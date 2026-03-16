from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import FeeRecord, NAVRecord


def calc_fee(db: Session, fund_id: int, fee_date):
    navs = db.query(NAVRecord).filter_by(fund_id=fund_id).order_by(NAVRecord.nav_date.asc()).all()
    if len(navs) < 2:
        raise ValueError("need >=2 nav records")
    gross_return = (Decimal(str(navs[-1].nav_per_share)) - Decimal(str(navs[0].nav_per_share))) / Decimal(str(navs[0].nav_per_share))
    fee_rate = Decimal("0.30") if gross_return > Decimal("0.15") else Decimal("0")
    fee_amount = Decimal(str(navs[-1].total_assets_usd)) * fee_rate
    row = FeeRecord(fund_id=fund_id, fee_date=fee_date, gross_return=gross_return, fee_rate=fee_rate, fee_amount_usd=fee_amount)
    db.add(row)
    db.commit()
    return row


def list_fees(db: Session):
    return db.query(FeeRecord).order_by(FeeRecord.fee_date.desc()).all()
