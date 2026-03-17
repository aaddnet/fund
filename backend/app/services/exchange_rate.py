from datetime import date, datetime, timezone
import requests
from sqlalchemy.orm import Session
from app.models import ExchangeRate


def fetch_and_save_rates(db: Session, base: str, quote: str, snapshot_date: date):
    exists = db.query(ExchangeRate).filter_by(base_currency=base, quote_currency=quote, snapshot_date=snapshot_date).first()
    if exists:
        return exists

    resp = requests.get(f"https://api.frankfurter.app/{snapshot_date.isoformat()}?from={base}&to={quote}", timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    rate = payload["rates"][quote]
    item = ExchangeRate(base_currency=base, quote_currency=quote, rate=rate, snapshot_date=snapshot_date, updated_at=datetime.now(timezone.utc))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_rates(db: Session):
    return db.query(ExchangeRate).order_by(ExchangeRate.snapshot_date.desc()).all()
