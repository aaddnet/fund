import csv
import io
from datetime import date, datetime, timezone
import logging
import requests
from sqlalchemy.orm import Session
from app.models import ExchangeRate

logger = logging.getLogger(__name__)

# Per-attempt timeout (seconds). The job retries up to _MAX_RETRIES times.
_REQUEST_TIMEOUT = 10
_MAX_RETRIES = 2


def fetch_and_save_rates(db: Session, base: str, quote: str, snapshot_date: date):
    exists = db.query(ExchangeRate).filter_by(base_currency=base, quote_currency=quote, snapshot_date=snapshot_date).first()
    if exists:
        return exists

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(
                f"https://api.frankfurter.app/{snapshot_date.isoformat()}?from={base}&to={quote}",
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
            rates = payload.get("rates", {})
            if quote not in rates:
                raise ValueError(f"Exchange rate for {base}/{quote} on {snapshot_date} not available from API")
            rate = rates[quote]
            item = ExchangeRate(
                base_currency=base,
                quote_currency=quote,
                rate=rate,
                snapshot_date=snapshot_date,
                source="frankfurter",
                updated_at=datetime.now(timezone.utc),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return item
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            logger.warning("FX fetch attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)

    raise last_exc  # type: ignore[misc]


def save_rates_csv(db: Session, content: bytes) -> list[ExchangeRate]:
    """Bulk-import FX rates from CSV. Expected columns: date,from_currency,to_currency,rate"""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    results = []
    for row in reader:
        try:
            snap_date = date.fromisoformat(str(row.get("date", "")).strip())
            base = str(row.get("from_currency", "")).strip().upper()
            quote = str(row.get("to_currency", "")).strip().upper()
            rate_val = float(str(row.get("rate", "")).strip())
            if not base or not quote:
                continue
            item = save_rate_manual(db, base, quote, rate_val, snap_date, source="csv")
            results.append(item)
        except (ValueError, KeyError):
            continue
    return results


def save_rate_manual(db: Session, base: str, quote: str, rate: float, snapshot_date: date, source: str = "manual") -> ExchangeRate:
    """Upsert an FX rate manually (offline fallback when external API is unreachable)."""
    base = base.upper().strip()
    quote = quote.upper().strip()
    existing = db.query(ExchangeRate).filter_by(
        base_currency=base, quote_currency=quote, snapshot_date=snapshot_date
    ).first()
    if existing:
        existing.rate = rate
        existing.source = source
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    item = ExchangeRate(
        base_currency=base,
        quote_currency=quote,
        rate=rate,
        snapshot_date=snapshot_date,
        source=source,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
