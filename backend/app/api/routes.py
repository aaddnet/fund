from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AssetPrice, Client, ExchangeRate, Fund, Position, Transaction
from app.schemas.common import FeeCalcRequest, NavCalcRequest, PriceFetchRequest, RateFetchRequest, ShareRequest
from app.services.exchange_rate import fetch_and_save_rates
from app.services.fee_service import calc_fee, list_fees
from app.services.import_service import confirm_batch, get_batch, list_batches, serialize_batch, upload_csv
from app.services.nav_engine import calc_nav, list_nav
from app.services.price_service import fetch_and_save_prices
from app.services.share_service import history, redeem, subscribe

router = APIRouter()
DEFAULT_PAGE = 1
DEFAULT_SIZE = 20
MAX_SIZE = 200


@router.post("/rates/fetch")
def fetch_rates(req: RateFetchRequest, db: Session = Depends(get_db)):
    return fetch_and_save_rates(db, req.base, req.quote, req.snapshot_date)


@router.get("/rates")
def get_rates(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    snapshot_date: Optional[date] = None,
    base: Optional[str] = None,
    quote: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ExchangeRate)
    if snapshot_date is not None:
        query = query.filter(ExchangeRate.snapshot_date == snapshot_date)
    if base:
        query = query.filter(ExchangeRate.base_currency == base.upper())
    if quote:
        query = query.filter(ExchangeRate.quote_currency == quote.upper())
    return _paginate(query.order_by(ExchangeRate.snapshot_date.desc(), ExchangeRate.id.desc()), page, size, _serialize_rate)


@router.post("/price/fetch")
def fetch_price(req: PriceFetchRequest, db: Session = Depends(get_db)):
    return fetch_and_save_prices(db, req.assets, req.snapshot_date)


@router.get("/price")
def list_price_records(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    snapshot_date: Optional[date] = None,
    asset_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AssetPrice)
    if snapshot_date is not None:
        query = query.filter(AssetPrice.snapshot_date == snapshot_date)
    if asset_code:
        query = query.filter(AssetPrice.asset_code == asset_code.upper())
    return _paginate(query.order_by(AssetPrice.snapshot_date.desc(), AssetPrice.id.desc()), page, size, _serialize_price)


@router.post("/nav/calc")
def run_nav(req: NavCalcRequest, db: Session = Depends(get_db)):
    try:
        return _serialize_nav(calc_nav(db, req.fund_id, req.nav_date))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nav")
def get_nav_records(fund_id: Optional[int] = None, db: Session = Depends(get_db)):
    return [_serialize_nav(item) for item in list_nav(db, fund_id=fund_id)]


@router.post("/share/subscribe")
def sub(req: ShareRequest, db: Session = Depends(get_db)):
    try:
        return subscribe(db, req.fund_id, req.client_id, req.tx_date, req.amount_usd)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/share/redeem")
def red(req: ShareRequest, db: Session = Depends(get_db)):
    try:
        return redeem(db, req.fund_id, req.client_id, req.tx_date, req.amount_usd)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/share/history")
def share_history(db: Session = Depends(get_db)):
    return history(db)


@router.post("/fee/calc")
def fee(req: FeeCalcRequest, db: Session = Depends(get_db)):
    try:
        return calc_fee(db, req.fund_id, req.fee_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fee")
def fee_list(db: Session = Depends(get_db)):
    return list_fees(db)


@router.get("/import")
def get_import_batches(db: Session = Depends(get_db)):
    return [serialize_batch(batch) for batch in list_batches(db)]


@router.get("/import/{batch_id}")
def get_import_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    return serialize_batch(batch)


@router.post("/import/upload")
async def upload_import_batch(
    source: str = Form(...),
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        payload = await file.read()
        batch = upload_csv(db, source=source, filename=file.filename or "upload.csv", account_id=account_id, content=payload)
        return serialize_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/{batch_id}/confirm")
def confirm_import_batch(batch_id: int, db: Session = Depends(get_db)):
    try:
        batch = confirm_batch(db, batch_id)
        return serialize_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund")
def list_funds(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
):
    query = db.query(Fund)
    return _paginate(query.order_by(Fund.id.asc()), page, size, _serialize_fund)


@router.get("/fund/{fund_id}")
def get_fund(fund_id: int, db: Session = Depends(get_db)):
    item = db.query(Fund).filter(Fund.id == fund_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fund not found.")
    return _serialize_fund(item)


@router.get("/client")
def list_clients(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
):
    query = db.query(Client)
    return _paginate(query.order_by(Client.id.asc()), page, size, _serialize_client)


@router.get("/client/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    item = db.query(Client).filter(Client.id == client_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Client not found.")
    return _serialize_client(item)


@router.get("/account")
def list_accounts(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Account)
    if fund_id is not None:
        query = query.filter(Account.fund_id == fund_id)
    if client_id is not None:
        query = query.filter(Account.client_id == client_id)
    return _paginate(query.order_by(Account.id.asc()), page, size, lambda item: _serialize_account(db, item))


@router.get("/account/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    item = db.query(Account).filter(Account.id == account_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Account not found.")
    return _serialize_account(db, item)


@router.get("/position")
def list_positions(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    fund_id: Optional[int] = None,
    account_id: Optional[int] = None,
    snapshot_date: Optional[date] = None,
    asset_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Position)
    if fund_id is not None:
        query = query.join(Account, Account.id == Position.account_id).filter(Account.fund_id == fund_id)
    if account_id is not None:
        query = query.filter(Position.account_id == account_id)
    if snapshot_date is not None:
        query = query.filter(Position.snapshot_date == snapshot_date)
    if asset_code:
        query = query.filter(Position.asset_code == asset_code.upper())
    return _paginate(query.order_by(Position.snapshot_date.desc(), Position.id.desc()), page, size, _serialize_position)


@router.get("/position/{position_id}")
def get_position(position_id: int, db: Session = Depends(get_db)):
    item = db.query(Position).filter(Position.id == position_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Position not found.")
    return _serialize_position(item)


@router.get("/transaction")
def list_transactions(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    fund_id: Optional[int] = None,
    account_id: Optional[int] = None,
    trade_date: Optional[date] = None,
    import_batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Transaction)
    if fund_id is not None:
        query = query.join(Account, Account.id == Transaction.account_id).filter(Account.fund_id == fund_id)
    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)
    if trade_date is not None:
        query = query.filter(Transaction.trade_date == trade_date)
    if import_batch_id is not None:
        query = query.filter(Transaction.import_batch_id == import_batch_id)
    return _paginate(query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()), page, size, _serialize_transaction)


@router.get("/transaction/{transaction_id}")
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return _serialize_transaction(item)


def _paginate(query, page: int, size: int, serializer):
    total = query.order_by(None).count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {
        "items": [serializer(item) for item in items],
        "pagination": {"page": page, "size": size, "total": total},
    }


def _serialize_fund(item: Fund) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "base_currency": item.base_currency,
        "total_shares": _decimal(item.total_shares),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_client(item: Client) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_account(db: Session, item: Account) -> dict:
    latest_snapshot_date = db.query(func.max(Position.snapshot_date)).filter(Position.account_id == item.id).scalar()
    position_count = db.query(func.count(Position.id)).filter(Position.account_id == item.id).scalar() or 0
    transaction_count = db.query(func.count(Transaction.id)).filter(Transaction.account_id == item.id).scalar() or 0
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "client_id": item.client_id,
        "broker": item.broker,
        "account_no": item.account_no,
        "position_count": int(position_count),
        "transaction_count": int(transaction_count),
        "latest_snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_position(item: Position) -> dict:
    return {
        "id": item.id,
        "account_id": item.account_id,
        "asset_code": item.asset_code,
        "quantity": _decimal(item.quantity),
        "average_cost": _decimal(item.average_cost),
        "currency": item.currency,
        "snapshot_date": item.snapshot_date.isoformat(),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_transaction(item: Transaction) -> dict:
    return {
        "id": item.id,
        "account_id": item.account_id,
        "trade_date": item.trade_date.isoformat(),
        "asset_code": item.asset_code,
        "quantity": _decimal(item.quantity),
        "price": _decimal(item.price),
        "currency": item.currency,
        "tx_type": item.tx_type,
        "fee": _decimal(item.fee),
        "import_batch_id": item.import_batch_id,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_nav(item) -> dict:
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "nav_date": item.nav_date.isoformat(),
        "total_assets_usd": _decimal(item.total_assets_usd),
        "total_shares": _decimal(item.total_shares),
        "nav_per_share": _decimal(item.nav_per_share),
        "is_locked": item.is_locked,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_rate(item: ExchangeRate) -> dict:
    return {
        "id": item.id,
        "base_currency": item.base_currency,
        "quote_currency": item.quote_currency,
        "rate": _decimal(item.rate),
        "snapshot_date": item.snapshot_date.isoformat(),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_price(item: AssetPrice) -> dict:
    return {
        "id": item.id,
        "asset_code": item.asset_code,
        "price_usd": _decimal(item.price_usd),
        "source": item.source,
        "snapshot_date": item.snapshot_date.isoformat(),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _decimal(value):
    if value is None:
        return None
    return float(Decimal(str(value)))


def _iso(value):
    return value.isoformat() if value else None
