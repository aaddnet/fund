from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import AssetPrice, AssetSnapshot, NAVRecord, Position


def calc_nav(db: Session, fund_id: int, nav_date):
    existing = db.query(NAVRecord).filter_by(fund_id=fund_id, nav_date=nav_date).first()
    if existing:
        return existing

    positions = db.query(Position).filter(Position.snapshot_date == nav_date).all()
    price_map = {p.asset_code: p for p in db.query(AssetPrice).filter_by(snapshot_date=nav_date).all()}

    total = Decimal("0")
    snapshots = []
    for pos in positions:
        price = Decimal(str(price_map[pos.asset_code].price_usd)) if pos.asset_code in price_map else Decimal("0")
        value = Decimal(str(pos.quantity)) * price
        total += value
        snapshots.append((pos.asset_code, pos.quantity, price, value))

    shares = Decimal("1")
    nav_per_share = total / shares if shares else Decimal("0")
    nav = NAVRecord(fund_id=fund_id, nav_date=nav_date, total_assets_usd=total, total_shares=shares, nav_per_share=nav_per_share, is_locked=True)
    db.add(nav)
    db.flush()

    for s in snapshots:
        db.add(AssetSnapshot(nav_record_id=nav.id, asset_code=s[0], quantity=s[1], price_usd=s[2], value_usd=s[3]))

    db.commit()
    db.refresh(nav)
    return nav


def list_nav(db: Session):
    return db.query(NAVRecord).order_by(NAVRecord.nav_date.desc()).all()
