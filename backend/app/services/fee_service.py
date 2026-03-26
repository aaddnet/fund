from __future__ import annotations

from decimal import Decimal, getcontext

from sqlalchemy.orm import Session

# Use 28-digit precision for all fee calculations to avoid rounding drift when
# exponentiating annualised returns (Python default is also 28, this makes it explicit).
getcontext().prec = 28

from app.models import FeeRecord, NAVRecord

ZERO = Decimal("0")
HURDLE_RATE = Decimal("0.08")
PERFORMANCE_FEE_SHARE = Decimal("0.30")
DAYS_IN_YEAR = Decimal("365")


def calc_fee(db: Session, fund_id: int, fee_date):
    navs = (
        db.query(NAVRecord)
        .filter(NAVRecord.fund_id == fund_id, NAVRecord.nav_date <= fee_date)
        .order_by(NAVRecord.nav_date.asc())
        .all()
    )
    if len(navs) < 2:
        raise ValueError("need >=2 nav records")

    nav_start_record = navs[-2]
    nav_end_record = navs[-1]
    nav_start = Decimal(str(nav_start_record.nav_per_share))
    nav_end_before_fee = Decimal(str(nav_end_record.total_assets_usd))
    nav_end_per_share = Decimal(str(nav_end_record.nav_per_share))

    if nav_start <= ZERO:
        raise ValueError("nav_start must be greater than 0")

    gross_return = (nav_end_per_share - nav_start) / nav_start
    day_count = max((nav_end_record.nav_date - nav_start_record.nav_date).days, 1)

    # 注意这里按实际期间年化，避免季度/半年记录直接拿期间收益当年收益。
    annual_return_pct = (Decimal("1") + gross_return) ** (DAYS_IN_YEAR / Decimal(day_count)) - Decimal("1")
    excess_return_pct = annual_return_pct - HURDLE_RATE
    if excess_return_pct < ZERO:
        excess_return_pct = ZERO

    fee_rate = excess_return_pct * PERFORMANCE_FEE_SHARE
    fee_base_usd = nav_end_before_fee
    fee_amount_usd = fee_base_usd * fee_rate
    nav_after_fee = nav_end_before_fee - fee_amount_usd

    row = db.query(FeeRecord).filter(FeeRecord.fund_id == fund_id, FeeRecord.fee_date == fee_date).first()
    if row is None:
        row = FeeRecord(fund_id=fund_id, fee_date=fee_date)
        db.add(row)

    row.gross_return = gross_return
    row.fee_rate = fee_rate
    row.fee_amount_usd = fee_amount_usd
    row.nav_start = nav_start
    row.nav_end_before_fee = nav_end_before_fee
    row.annual_return_pct = annual_return_pct
    row.excess_return_pct = excess_return_pct
    row.fee_base_usd = fee_base_usd
    row.nav_after_fee = nav_after_fee
    row.applied_date = fee_date

    db.commit()
    db.refresh(row)
    return serialize_fee(row)


def list_fees(db: Session):
    return [serialize_fee(row) for row in db.query(FeeRecord).order_by(FeeRecord.fee_date.desc(), FeeRecord.id.desc()).all()]


def serialize_fee(row: FeeRecord) -> dict:
    return {
        "id": row.id,
        "fund_id": row.fund_id,
        "fee_date": row.fee_date.isoformat(),
        "gross_return": float(Decimal(str(row.gross_return))),
        "fee_rate": float(Decimal(str(row.fee_rate))),
        "fee_amount_usd": float(Decimal(str(row.fee_amount_usd))),
        "nav_start": float(Decimal(str(row.nav_start))) if row.nav_start is not None else None,
        "nav_end_before_fee": float(Decimal(str(row.nav_end_before_fee))) if row.nav_end_before_fee is not None else None,
        "annual_return_pct": float(Decimal(str(row.annual_return_pct))) if row.annual_return_pct is not None else None,
        "excess_return_pct": float(Decimal(str(row.excess_return_pct))) if row.excess_return_pct is not None else None,
        "fee_base_usd": float(Decimal(str(row.fee_base_usd))) if row.fee_base_usd is not None else None,
        "nav_after_fee": float(Decimal(str(row.nav_after_fee))) if row.nav_after_fee is not None else None,
        "applied_date": row.applied_date.isoformat() if row.applied_date else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
