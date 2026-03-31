import csv
import io
from datetime import date, datetime, timezone
import requests
import yfinance as yf
from sqlalchemy.orm import Session
from app.models import AssetPrice


def _fetch_price(asset_code: str) -> tuple[float, str]:
    try:
        ticker = yf.Ticker(asset_code)
        p = ticker.fast_info.last_price
        if p:
            return float(p), "yfinance"
    except Exception:
        pass
    r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={asset_code}&vs_currencies=usd", timeout=15)
    if r.ok:
        data = r.json()
        if asset_code in data:
            return float(data[asset_code]["usd"]), "coingecko"
    raise ValueError(f"no price source for {asset_code}")


def save_price_manual(db: Session, asset_code: str, price_usd: float, snapshot_date: date) -> AssetPrice:
    """Manually upsert a single asset price."""
    asset_code = asset_code.strip().upper()
    existing = db.query(AssetPrice).filter_by(asset_code=asset_code, snapshot_date=snapshot_date).first()
    if existing:
        existing.price_usd = price_usd
        existing.source = "manual"
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    row = AssetPrice(asset_code=asset_code, price_usd=price_usd, source="manual", snapshot_date=snapshot_date, updated_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_prices_csv(db: Session, content: bytes) -> list[AssetPrice]:
    """Bulk-import asset prices from CSV. Expected columns: asset_code,price_usd,price_date"""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    results = []
    for row in reader:
        try:
            asset_code = str(row.get("asset_code", "")).strip().upper()
            price_usd = float(str(row.get("price_usd", "")).strip())
            snap_date = date.fromisoformat(str(row.get("price_date", "")).strip())
            if not asset_code:
                continue
            item = save_price_manual(db, asset_code, price_usd, snap_date)
            results.append(item)
        except (ValueError, KeyError):
            continue
    return results


def fetch_and_save_prices(db: Session, assets: list[str], snapshot_date):
    out = []
    for asset in assets:
        exists = db.query(AssetPrice).filter_by(asset_code=asset, snapshot_date=snapshot_date).first()
        if exists:
            out.append(exists)
            continue
        price, source = _fetch_price(asset)
        row = AssetPrice(asset_code=asset, price_usd=price, source=source, snapshot_date=snapshot_date, updated_at=datetime.now(timezone.utc))
        db.add(row)
        out.append(row)
    db.commit()
    return out
