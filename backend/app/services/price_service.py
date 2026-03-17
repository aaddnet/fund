from datetime import UTC, datetime
import requests
import yfinance as yf
from sqlalchemy.orm import Session
from app.models import AssetPrice


def _fetch_price(asset_code: str) -> tuple[float, str]:
    try:
        ticker = yf.Ticker(asset_code)
        p = ticker.fast_info.get("lastPrice")
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
