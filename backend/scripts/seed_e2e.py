from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from app.db import SessionLocal
from app.models import Account, AssetPrice, Client, ExchangeRate, Fund, NAVRecord, Position, ShareTransaction
from app.services.auth import bootstrap_auth_users


def upsert(db, model, identity: dict, payload: dict):
    row = db.query(model).filter_by(**identity).first()
    if row is None:
        row = model(**payload)
        db.add(row)
        return row
    for key, value in payload.items():
        setattr(row, key, value)
    return row


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / 'alembic.ini'))
    config.set_main_option('script_location', str(backend_dir / 'alembic'))
    command.upgrade(config, 'head')

    db = SessionLocal()
    try:
        upsert(db, Fund, {'id': 1}, {'id': 1, 'name': 'Demo Fund', 'base_currency': 'USD', 'total_shares': 100})
        upsert(db, Fund, {'id': 2}, {'id': 2, 'name': 'Other Fund', 'base_currency': 'USD', 'total_shares': 50})
        upsert(db, Client, {'id': 1}, {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'})
        upsert(db, Client, {'id': 2}, {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'})
        upsert(db, Account, {'id': 1}, {'id': 1, 'fund_id': 1, 'client_id': 1, 'broker': 'IB', 'account_no': 'ACC-001'})
        upsert(db, Account, {'id': 2}, {'id': 2, 'fund_id': 2, 'client_id': 2, 'broker': 'HK Broker', 'account_no': 'ACC-002'})

        for payload in [
            {'id': 1, 'fund_id': 1, 'nav_date': date(2026, 3, 31), 'total_assets_usd': 1500, 'total_shares': 100, 'nav_per_share': 15, 'is_locked': True},
            {'id': 2, 'fund_id': 1, 'nav_date': date(2026, 6, 30), 'total_assets_usd': 2000, 'total_shares': 100, 'nav_per_share': 20, 'is_locked': True},
            {'id': 3, 'fund_id': 2, 'nav_date': date(2026, 6, 30), 'total_assets_usd': 2500, 'total_shares': 50, 'nav_per_share': 50, 'is_locked': True},
        ]:
            upsert(db, NAVRecord, {'id': payload['id']}, payload)

        for payload in [
            {'id': 1, 'fund_id': 1, 'client_id': 1, 'tx_date': date(2026, 3, 31), 'tx_type': 'subscribe', 'amount_usd': 300, 'shares': 20, 'nav_at_date': 15},
            {'id': 2, 'fund_id': 1, 'client_id': 1, 'tx_date': date(2026, 6, 30), 'tx_type': 'subscribe', 'amount_usd': 400, 'shares': 20, 'nav_at_date': 20},
            {'id': 3, 'fund_id': 2, 'client_id': 2, 'tx_date': date(2026, 6, 30), 'tx_type': 'subscribe', 'amount_usd': 500, 'shares': 10, 'nav_at_date': 50},
        ]:
            upsert(db, ShareTransaction, {'id': payload['id']}, payload)

        for identity, payload in [
            ({'account_id': 1, 'asset_code': 'AAPL', 'snapshot_date': date(2026, 6, 30)}, {'account_id': 1, 'asset_code': 'AAPL', 'quantity': 10, 'average_cost': 150, 'currency': 'USD', 'snapshot_date': date(2026, 6, 30)}),
            ({'account_id': 1, 'asset_code': 'BTC', 'snapshot_date': date(2026, 6, 30)}, {'account_id': 1, 'asset_code': 'BTC', 'quantity': 0.5, 'average_cost': 60000, 'currency': 'USD', 'snapshot_date': date(2026, 6, 30)}),
            ({'account_id': 2, 'asset_code': '0700.HK', 'snapshot_date': date(2026, 6, 30)}, {'account_id': 2, 'asset_code': '0700.HK', 'quantity': 100, 'average_cost': 300, 'currency': 'HKD', 'snapshot_date': date(2026, 6, 30)}),
        ]:
            upsert(db, Position, identity, payload)

        for identity, payload in [
            ({'asset_code': 'AAPL', 'snapshot_date': date(2026, 6, 30)}, {'asset_code': 'AAPL', 'price_usd': 220, 'source': 'seed', 'snapshot_date': date(2026, 6, 30)}),
            ({'asset_code': 'BTC', 'snapshot_date': date(2026, 6, 30)}, {'asset_code': 'BTC', 'price_usd': 90000, 'source': 'seed', 'snapshot_date': date(2026, 6, 30)}),
        ]:
            upsert(db, AssetPrice, identity, payload)

        upsert(db, ExchangeRate, {'base_currency': 'HKD', 'quote_currency': 'USD', 'snapshot_date': date(2026, 6, 30)}, {'base_currency': 'HKD', 'quote_currency': 'USD', 'rate': 0.127, 'snapshot_date': date(2026, 6, 30)})
        db.commit()
        bootstrap_auth_users(db)
        db.commit()
    finally:
        db.close()


if __name__ == '__main__':
    main()
