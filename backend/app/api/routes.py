from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status, BackgroundTasks
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Account, AssetPrice, AuthUser, Client, ExchangeRate, FeeRecord, Fund, NAVRecord, Position, Transaction
from app.schemas.common import (
    AuthPasswordChangeRequest,
    AuthPasswordResetRequest,
    AuthUserCreateRequest,
    AuthUserUpdateRequest,
    ClientCreateRequest,
    ClientUpdateRequest,
    AccountCreateRequest,
    AccountUpdateRequest,
    FeeCalcRequest,
    FundCreateRequest,
    FundUpdateRequest,
    NavCalcRequest,
    PriceFetchRequest,
    RateFetchRequest,
    RateManualRequest,
    ShareRequest,
)
from app.services.audit import list_audit_logs, record_audit
from app.services.auth import (
    ROLE_CLIENT_READONLY,
    Actor,
    admin_reset_password,
    apply_client_scope_filters,
    change_password,
    create_auth_user,
    get_actor,
    list_auth_users,
    login_with_password,
    refresh_access_token,
    require_client_scope,
    require_permissions,
    require_roles,
    revoke_session,
    update_auth_user,
    permissions_for_role,
)
from app.services.exchange_rate import fetch_and_save_rates, save_rate_manual
from app.services.fee_service import calc_fee, list_fees
from app.services.import_service import confirm_batch, get_batch, list_batches, serialize_batch, upload_csv
from app.services.nav_engine import calc_nav, list_nav
from app.services.price_service import fetch_and_save_prices
from app.services.scheduler import SCHEDULER_JOB_FX_WEEKLY, list_job_runs, run_weekly_fx_job
from app.services.share_service import balances, history, redeem, subscribe

router = APIRouter()
DEFAULT_PAGE = 1
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_SIZE = 20
MAX_SIZE = 200


@router.post("/auth/login")
def auth_login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    session = login_with_password(db, username=username, password=password)
    payload = _serialize_auth_session(session)
    _set_auth_cookies(response, session)
    return payload


@router.post("/auth/refresh")
def auth_refresh(request: Request, response: Response, refresh_token: Optional[str] = Form(default=None), db: Session = Depends(get_db)):
    effective_refresh_token = refresh_token or request.cookies.get(settings.auth_refresh_cookie_name)
    if not effective_refresh_token:
        raise HTTPException(status_code=401, detail="refresh token required")
    session = refresh_access_token(db, refresh_token=effective_refresh_token)
    payload = _serialize_auth_session(session)
    _set_auth_cookies(response, session)
    return payload


@router.get("/auth/csrf")
def auth_csrf():
    return {"header_name": settings.auth_csrf_header_name, "cookie_name": settings.auth_csrf_cookie_name}


@router.get("/auth/me")
def auth_me(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    user = db.query(AuthUser).filter(AuthUser.id == actor.user_id).first() if actor.user_id else None
    return {
        "actor": {
            "role": actor.role,
            "operator_id": actor.operator_id,
            "client_scope_id": actor.client_scope_id,
            "auth_mode": actor.auth_mode,
            "session_id": actor.session_id,
            "username": actor.username,
            "permissions": list(actor.permissions),
        },
        "user": _serialize_auth_user(user) if user else None,
    }


@router.post("/auth/logout", status_code=204)
def auth_logout(response: Response, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    if actor.session_id:
        revoke_session(db, actor.session_id)
    _clear_auth_cookies(response)
    response.status_code = 204
    return response




@router.post("/rates/fetch")
def fetch_rates(req: RateFetchRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "rates.write")
    row = fetch_and_save_rates(db, req.base, req.quote, req.snapshot_date)
    record_audit(
        db,
        actor,
        action="rate.fetch",
        entity_type="exchange_rate",
        entity_id=str(row.id),
        detail={"base": req.base.upper(), "quote": req.quote.upper(), "snapshot_date": req.snapshot_date.isoformat()},
    )
    return row


@router.get("/rates")
def get_rates(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    snapshot_date: Optional[date] = None,
    base: Optional[str] = None,
    quote: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "rates.read")
    query = db.query(ExchangeRate)
    if snapshot_date is not None:
        query = query.filter(ExchangeRate.snapshot_date == snapshot_date)
    if base:
        query = query.filter(ExchangeRate.base_currency == base.upper())
    if quote:
        query = query.filter(ExchangeRate.quote_currency == quote.upper())
    return _paginate(query.order_by(ExchangeRate.snapshot_date.desc(), ExchangeRate.id.desc()), page, size, _serialize_rate)


@router.post("/rates/manual")
def upsert_rate_manual(req: RateManualRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Manually upsert an FX rate. Useful when the external API is unreachable (e.g. in Docker without outbound network)."""
    require_permissions(actor, "rates.write")
    row = save_rate_manual(db, req.base, req.quote, float(req.rate), req.snapshot_date)
    record_audit(
        db,
        actor,
        action="rate.manual",
        entity_type="exchange_rate",
        entity_id=str(row.id),
        detail={"base": req.base, "quote": req.quote, "rate": float(req.rate), "snapshot_date": req.snapshot_date.isoformat()},
    )
    return _serialize_rate(row)


@router.post("/price/fetch")
def fetch_price(req: PriceFetchRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "price.write")
    rows = fetch_and_save_prices(db, req.assets, req.snapshot_date)
    record_audit(
        db,
        actor,
        action="price.fetch",
        entity_type="asset_price_batch",
        entity_id=req.snapshot_date.isoformat(),
        detail={"assets": [asset.upper() for asset in req.assets], "snapshot_date": req.snapshot_date.isoformat()},
    )
    return rows


@router.get("/price")
def list_price_records(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    snapshot_date: Optional[date] = None,
    asset_code: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "price.read")
    query = db.query(AssetPrice)
    if snapshot_date is not None:
        query = query.filter(AssetPrice.snapshot_date == snapshot_date)
    if asset_code:
        query = query.filter(AssetPrice.asset_code == asset_code.upper())
    return _paginate(query.order_by(AssetPrice.snapshot_date.desc(), AssetPrice.id.desc()), page, size, _serialize_price)


@router.post("/nav/calc")
def run_nav(req: NavCalcRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    try:
        row = calc_nav(db, req.fund_id, req.nav_date)
        record_audit(
            db,
            actor,
            action="nav.calc",
            entity_type="nav_record",
            entity_id=str(row.id),
            detail={"fund_id": req.fund_id, "nav_date": req.nav_date.isoformat()},
        )
        return _serialize_nav(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nav")
def get_nav_records(fund_id: Optional[int] = None, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.read")
    if actor.role == ROLE_CLIENT_READONLY and fund_id is None:
        fund_ids = _client_fund_ids(db, actor.client_scope_id)
        return [_serialize_nav(item) for item in list_nav(db) if item.fund_id in fund_ids]
    return [_serialize_nav(item) for item in list_nav(db, fund_id=fund_id)]


@router.post("/share/subscribe")
def sub(req: ShareRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "shares.write")
    try:
        payload = subscribe(db, req.fund_id, req.client_id, req.tx_date, req.amount_usd)
        record_audit(
            db,
            actor,
            action="share.subscribe",
            entity_type="share_transaction",
            entity_id=str(payload["id"]),
            detail={"fund_id": req.fund_id, "client_id": req.client_id, "tx_date": req.tx_date.isoformat(), "amount_usd": float(req.amount_usd)},
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/share/redeem")
def red(req: ShareRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "shares.write")
    try:
        payload = redeem(db, req.fund_id, req.client_id, req.tx_date, req.amount_usd)
        record_audit(
            db,
            actor,
            action="share.redeem",
            entity_type="share_transaction",
            entity_id=str(payload["id"]),
            detail={"fund_id": req.fund_id, "client_id": req.client_id, "tx_date": req.tx_date.isoformat(), "amount_usd": float(req.amount_usd)},
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/share/history")
def share_history(
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "shares.read")
    fund_id, client_id = apply_client_scope_filters(actor, fund_id, client_id)
    return history(db, fund_id=fund_id, client_id=client_id, tx_type=tx_type, date_from=date_from, date_to=date_to)


@router.get("/share/balances")
def share_balances(
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "shares.read")
    fund_id, client_id = apply_client_scope_filters(actor, fund_id, client_id)
    return balances(db, fund_id=fund_id, client_id=client_id)


@router.post("/fee/calc")
def fee(req: FeeCalcRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "fees.write")
    try:
        payload = calc_fee(db, req.fund_id, req.fee_date)
        record_audit(
            db,
            actor,
            action="fee.calc",
            entity_type="fee_record",
            entity_id=str(payload["id"]),
            detail={"fund_id": req.fund_id, "fee_date": req.fee_date.isoformat()},
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fee")
def fee_list(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "fees.read")
    return list_fees(db)


@router.get("/import")
def get_import_batches(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.read")
    return [serialize_batch(batch) for batch in list_batches(db)]


@router.get("/import/{batch_id}")
def get_import_batch(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.read")
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
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "import.write")
    try:
        payload = await file.read()
        batch = upload_csv(db, source=source, filename=file.filename or "upload.csv", account_id=account_id, content=payload)
        record_audit(
            db,
            actor,
            action="import.upload",
            entity_type="import_batch",
            entity_id=str(batch.id),
            detail={"source": source, "account_id": account_id, "filename": file.filename or "upload.csv", "status": batch.status},
        )
        return serialize_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/{batch_id}/confirm")
def confirm_import_batch(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.write")
    try:
        batch = confirm_batch(db, batch_id)
        record_audit(
            db,
            actor,
            action="import.confirm",
            entity_type="import_batch",
            entity_id=str(batch.id),
            detail={"account_id": batch.account_id, "confirmed_count": batch.confirmed_count, "status": batch.status},
        )
        return serialize_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund")
def list_funds(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "nav.read")
    query = db.query(Fund)
    if actor.role == ROLE_CLIENT_READONLY:
        fund_ids = _client_fund_ids(db, actor.client_scope_id)
        query = query.filter(Fund.id.in_(fund_ids))
    return _paginate(query.order_by(Fund.id.asc()), page, size, _serialize_fund)


@router.get("/fund/{fund_id}")
def get_fund(fund_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.read")
    if actor.role == ROLE_CLIENT_READONLY and fund_id not in _client_fund_ids(db, actor.client_scope_id):
        raise HTTPException(status_code=403, detail="fund scope mismatch")
    item = db.query(Fund).filter(Fund.id == fund_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fund not found.")
    return _serialize_fund(item)


@router.post("/fund")
def create_fund(req: FundCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    fund = Fund(name=req.name.strip(), base_currency=req.base_currency.upper().strip())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    record_audit(db, actor, action="fund.create", entity_type="fund", entity_id=str(fund.id), detail={"name": fund.name, "base_currency": fund.base_currency})
    return _serialize_fund(fund)


@router.patch("/fund/{fund_id}")
def update_fund(fund_id: int, req: FundUpdateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found.")
    if req.name is not None:
        fund.name = req.name.strip()
    if req.base_currency is not None:
        fund.base_currency = req.base_currency.upper().strip()
    db.commit()
    db.refresh(fund)
    record_audit(db, actor, action="fund.update", entity_type="fund", entity_id=str(fund.id), detail={"name": fund.name})
    return _serialize_fund(fund)


@router.get("/client")
def list_clients(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    fund_id: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "clients.read")
    query = db.query(Client)
    if actor.role == ROLE_CLIENT_READONLY:
        query = query.filter(Client.id == actor.client_scope_id)
    if fund_id is not None:
        query = query.join(Account, Account.client_id == Client.id).filter(Account.fund_id == fund_id).distinct()
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Client.name.ilike(like)) | (Client.email.ilike(like)))
    return _paginate(query.order_by(Client.id.asc()), page, size, lambda item: _serialize_client(db, item))


@router.get("/client/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.read")
    require_client_scope(actor, client_id)
    item = db.query(Client).filter(Client.id == client_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Client not found.")
    return _serialize_client(db, item)


@router.post("/client")
def create_client(req: ClientCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    client = Client(name=req.name, email=req.email)
    db.add(client)
    db.commit()
    db.refresh(client)
    record_audit(db, actor, action="client.create", entity_type="client", entity_id=str(client.id), detail={"name": client.name})
    return _serialize_client(db, client)


@router.patch("/client/{client_id}")
def update_client(client_id: int, req: ClientUpdateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    require_client_scope(actor, client_id)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    if req.name is not None:
        client.name = req.name
    if req.email is not None:
        client.email = req.email
    db.commit()
    db.refresh(client)
    record_audit(db, actor, action="client.update", entity_type="client", entity_id=str(client.id), detail={"name": client.name})
    return _serialize_client(db, client)


@router.get("/account")
def list_accounts(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    broker: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    fund_id, client_id = apply_client_scope_filters(actor, fund_id, client_id)
    query = db.query(Account)
    if fund_id is not None:
        query = query.filter(Account.fund_id == fund_id)
    if client_id is not None:
        query = query.filter(Account.client_id == client_id)
    if broker:
        query = query.filter(Account.broker.ilike(f"%{broker.strip()}%"))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Account.account_no.ilike(like)) | (Account.broker.ilike(like)))
    return _paginate(query.order_by(Account.id.asc()), page, size, lambda item: _serialize_account(db, item))


@router.get("/account/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.read")
    item = db.query(Account).filter(Account.id == account_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Account not found.")
    require_client_scope(actor, item.client_id)
    return _serialize_account(db, item)


@router.post("/account")
def create_account(req: AccountCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.write")
    account = Account(fund_id=req.fund_id, client_id=req.client_id, broker=req.broker, account_no=req.account_no)
    db.add(account)
    db.commit()
    db.refresh(account)
    record_audit(db, actor, action="account.create", entity_type="account", entity_id=str(account.id), detail={"account_no": account.account_no})
    return _serialize_account(db, account)


@router.patch("/account/{account_id}")
def update_account(account_id: int, req: AccountUpdateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.write")
    item = db.query(Account).filter(Account.id == account_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Account not found.")
    require_client_scope(actor, item.client_id)
    if req.fund_id is not None:
        item.fund_id = req.fund_id
    if req.client_id is not None:
        item.client_id = req.client_id
    if req.broker is not None:
        item.broker = req.broker
    if req.account_no is not None:
        item.account_no = req.account_no
    db.commit()
    db.refresh(item)
    record_audit(db, actor, action="account.update", entity_type="account", entity_id=str(item.id), detail={"account_no": item.account_no})
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
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Position)
    if fund_id is not None:
        query = query.join(Account, Account.id == Position.account_id).filter(Account.fund_id == fund_id)
    if account_id is not None:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            require_client_scope(actor, account.client_id)
        query = query.filter(Position.account_id == account_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        query = query.join(Account, Account.id == Position.account_id).filter(Account.client_id == actor.client_scope_id)
    if snapshot_date is not None:
        query = query.filter(Position.snapshot_date == snapshot_date)
    if asset_code:
        query = query.filter(Position.asset_code == asset_code.upper())
    return _paginate(query.order_by(Position.snapshot_date.desc(), Position.id.desc()), page, size, _serialize_position)


@router.get("/position/{position_id}")
def get_position(position_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.read")
    item = db.query(Position).filter(Position.id == position_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Position not found.")
    account = db.query(Account).filter(Account.id == item.account_id).first()
    if account:
        require_client_scope(actor, account.client_id)
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
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Transaction)
    if fund_id is not None:
        query = query.join(Account, Account.id == Transaction.account_id).filter(Account.fund_id == fund_id)
    if account_id is not None:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            require_client_scope(actor, account.client_id)
        query = query.filter(Transaction.account_id == account_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        query = query.join(Account, Account.id == Transaction.account_id).filter(Account.client_id == actor.client_scope_id)
    if trade_date is not None:
        query = query.filter(Transaction.trade_date == trade_date)
    if import_batch_id is not None:
        query = query.filter(Transaction.import_batch_id == import_batch_id)
    return _paginate(query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()), page, size, _serialize_transaction)


@router.get("/transaction/{transaction_id}")
def get_transaction(transaction_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.read")
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    account = db.query(Account).filter(Account.id == item.account_id).first()
    if account:
        require_client_scope(actor, account.client_id)
    return _serialize_transaction(item)


@router.get("/customer/{client_id}")
def get_customer_view(client_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "customer.read")
    require_client_scope(actor, client_id)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    account_rows = db.query(Account).filter(Account.client_id == client_id).order_by(Account.id.asc()).all()
    fund_ids = sorted({account.fund_id for account in account_rows})
    share_balance_rows = balances(db, client_id=client_id)
    share_history_rows = history(db, client_id=client_id)
    nav_rows = [_serialize_nav(item) for item in list_nav(db)]
    relevant_nav = [row for row in nav_rows if row["fund_id"] in fund_ids]

    return {
        "client": _serialize_client(db, client),
        "accounts": [_serialize_account(db, account) for account in account_rows],
        "share_balances": share_balance_rows,
        "share_history": share_history_rows,
        # 只返回客户有关基金的 NAV 历史，保持 customer 视图聚焦且只读。
        "nav_history": relevant_nav,
    }


@router.get("/reports/overview")
def get_reports_overview(
    period_type: str = Query("quarter"),
    period_value: str = Query(...),
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "reports.read")
    fund_id, client_id = apply_client_scope_filters(actor, fund_id, client_id)
    start_date, end_date = _resolve_period(period_type, period_value)

    share_rows = history(db, fund_id=fund_id, client_id=client_id, tx_type=tx_type, date_from=start_date, date_to=end_date)

    nav_query = db.query(NAVRecord).filter(and_(NAVRecord.nav_date >= start_date, NAVRecord.nav_date <= end_date))
    if fund_id is not None:
        nav_query = nav_query.filter(NAVRecord.fund_id == fund_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        nav_query = nav_query.filter(NAVRecord.fund_id.in_(_client_fund_ids(db, actor.client_scope_id)))
    nav_rows = [_serialize_nav(item) for item in nav_query.order_by(NAVRecord.nav_date.desc(), NAVRecord.id.desc()).all()]

    fee_rows = []
    if actor.role != ROLE_CLIENT_READONLY:
        fee_query = db.query(FeeRecord).filter(and_(FeeRecord.fee_date >= start_date, FeeRecord.fee_date <= end_date))
        if fund_id is not None:
            fee_query = fee_query.filter(FeeRecord.fund_id == fund_id)
        fee_rows = [_serialize_fee(item) for item in fee_query.order_by(FeeRecord.fee_date.desc(), FeeRecord.id.desc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    transaction_query = transaction_query.join(Account, Account.id == Transaction.account_id)
    if fund_id is not None:
        transaction_query = transaction_query.filter(Account.fund_id == fund_id)
    if client_id is not None:
        transaction_query = transaction_query.filter(Account.client_id == client_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        transaction_query = transaction_query.filter(Account.client_id == actor.client_scope_id)
    transaction_rows = [_serialize_transaction(item) for item in transaction_query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()).all()]

    subscribe_amount = sum(item["amount_usd"] for item in share_rows if item["tx_type"] == "subscribe")
    redeem_amount = sum(item["amount_usd"] for item in share_rows if item["tx_type"] == "redeem")
    unique_funds = sorted({item["fund_id"] for item in share_rows})
    unique_clients = sorted({item["client_id"] for item in share_rows})

    return {
        "filters": {
            "period_type": period_type,
            "period_value": period_value,
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "fund_id": fund_id,
            "client_id": client_id,
            "tx_type": tx_type,
            "viewer_role": actor.role,
        },
        "summary": {
            "share_tx_count": len(share_rows),
            "subscription_amount_usd": subscribe_amount,
            "redemption_amount_usd": redeem_amount,
            "net_share_flow_usd": subscribe_amount - redeem_amount,
            "nav_record_count": len(nav_rows),
            "fee_record_count": len(fee_rows),
            "transaction_count": len(transaction_rows),
            "fund_count": len(unique_funds),
            "client_count": len(unique_clients),
            "avg_nav_per_share": round(sum(item["nav_per_share"] for item in nav_rows) / len(nav_rows), 6) if nav_rows else 0,
            "latest_nav_date": nav_rows[0]["nav_date"] if nav_rows else None,
        },
        "share_history": share_rows,
        "nav_records": nav_rows,
        "fee_records": fee_rows,
        "transactions": transaction_rows,
        "breakdowns": {
            "by_fund": _aggregate_report_dimension(share_rows, "fund_id"),
            "by_client": _aggregate_report_dimension(share_rows, "client_id"),
            "by_tx_type": _aggregate_report_dimension(share_rows, "tx_type"),
            "transactions_by_asset": _aggregate_transaction_assets(transaction_rows),
            "nav_by_fund": _aggregate_nav_by_fund(nav_rows),
        },
        "series": {
            "share_flow_by_date": _aggregate_share_flow_series(share_rows),
            "nav_trend": _aggregate_nav_series(nav_rows),
        },
    }


@router.get("/reports/export")
def export_reports(
    period_type: str = Query("quarter"),
    period_value: str = Query(...),
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "reports.read")
    fund_id, client_id = apply_client_scope_filters(actor, fund_id, client_id)
    start_date, end_date = _resolve_period(period_type, period_value)

    share_rows = history(db, fund_id=fund_id, client_id=client_id, date_from=start_date, date_to=end_date)

    nav_query = db.query(NAVRecord).filter(and_(NAVRecord.nav_date >= start_date, NAVRecord.nav_date <= end_date))
    if fund_id is not None:
        nav_query = nav_query.filter(NAVRecord.fund_id == fund_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        nav_query = nav_query.filter(NAVRecord.fund_id.in_(_client_fund_ids(db, actor.client_scope_id)))
    nav_rows = [_serialize_nav(item) for item in nav_query.order_by(NAVRecord.nav_date.asc()).all()]

    fee_rows = []
    if actor.role != ROLE_CLIENT_READONLY:
        fee_query = db.query(FeeRecord).filter(and_(FeeRecord.fee_date >= start_date, FeeRecord.fee_date <= end_date))
        if fund_id is not None:
            fee_query = fee_query.filter(FeeRecord.fund_id == fund_id)
        fee_rows = [_serialize_fee(item) for item in fee_query.order_by(FeeRecord.fee_date.asc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    if fund_id is not None or client_id is not None or actor.role == ROLE_CLIENT_READONLY:
        transaction_query = transaction_query.join(Account, Account.id == Transaction.account_id)
        if fund_id is not None:
            transaction_query = transaction_query.filter(Account.fund_id == fund_id)
        if client_id is not None:
            transaction_query = transaction_query.filter(Account.client_id == client_id)
        elif actor.role == ROLE_CLIENT_READONLY:
            transaction_query = transaction_query.filter(Account.client_id == actor.client_scope_id)
    transaction_rows = [_serialize_transaction(item) for item in transaction_query.order_by(Transaction.trade_date.asc()).all()]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["# Share Flow"])
    writer.writerow(["tx_date", "fund_id", "client_id", "tx_type", "amount_usd", "shares", "nav_at_date"])
    for row in share_rows:
        writer.writerow([row["tx_date"], row["fund_id"], row["client_id"], row["tx_type"], row["amount_usd"], row["shares"], row["nav_at_date"]])

    writer.writerow([])
    writer.writerow(["# NAV Records"])
    writer.writerow(["nav_date", "fund_id", "total_assets_usd", "total_shares", "nav_per_share"])
    for row in nav_rows:
        writer.writerow([row["nav_date"], row["fund_id"], row["total_assets_usd"], row["total_shares"], row["nav_per_share"]])

    if fee_rows:
        writer.writerow([])
        writer.writerow(["# Fee Records"])
        writer.writerow(["fee_date", "fund_id", "gross_return", "annual_return_pct", "excess_return_pct", "fee_rate", "fee_amount_usd", "nav_after_fee"])
        for row in fee_rows:
            writer.writerow([row["fee_date"], row["fund_id"], row["gross_return"], row["annual_return_pct"], row["excess_return_pct"], row["fee_rate"], row["fee_amount_usd"], row["nav_after_fee"]])

    writer.writerow([])
    writer.writerow(["# Transactions"])
    writer.writerow(["trade_date", "account_id", "asset_code", "quantity", "price", "currency", "tx_type", "fee"])
    for row in transaction_rows:
        writer.writerow([row["trade_date"], row["account_id"], row["asset_code"], row["quantity"], row["price"], row["currency"], row["tx_type"], row["fee"]])

    filename = f"report_{period_value}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/audit")
def get_audit(
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "audit.read")
    client_scope_id = actor.client_scope_id if actor.role == ROLE_CLIENT_READONLY else None
    return list_audit_logs(db, limit=limit, action=action, client_scope_id=client_scope_id)


@router.get("/scheduler/jobs")
def get_scheduler_runs(
    limit: int = Query(20, ge=1, le=100),
    job_name: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "scheduler.read")
    return list_job_runs(db, limit=limit, job_name=job_name)


@router.post("/scheduler/jobs/fx-weekly/run")
def trigger_scheduler_job(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "scheduler.run")
    payload = run_weekly_fx_job(trigger_source="manual")
    record_audit(
        db,
        actor,
        action="scheduler.trigger",
        entity_type="scheduler_job",
        entity_id=SCHEDULER_JOB_FX_WEEKLY,
        detail={"job_name": SCHEDULER_JOB_FX_WEEKLY, "trigger_source": "manual", "result_count": len(payload["fetched"])},
    )
    return payload


def _client_fund_ids(db: Session, client_id: Optional[int]) -> list[int]:
    if client_id is None:
        return []
    return sorted({row[0] for row in db.query(Account.fund_id).filter(Account.client_id == client_id).all()})


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


def _serialize_client(db: Session, item: Client) -> dict:
    account_rows = db.query(Account).filter(Account.client_id == item.id).all()
    fund_ids = sorted({account.fund_id for account in account_rows})
    share_balance_rows = balances(db, client_id=item.id)
    total_share_balance = sum(row["share_balance"] for row in share_balance_rows)
    share_history_rows = history(db, client_id=item.id)
    latest_tx_date = db.query(func.max(Transaction.trade_date)).join(Account, Account.id == Transaction.account_id).filter(Account.client_id == item.id).scalar()
    latest_share_event_date = share_history_rows[0]["tx_date"] if share_history_rows else None

    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "account_count": len(account_rows),
        "fund_count": len(fund_ids),
        "fund_ids": fund_ids,
        "total_share_balance": total_share_balance,
        "share_tx_count": len(share_history_rows),
        "latest_trade_date": latest_tx_date.isoformat() if latest_tx_date else None,
        "latest_share_tx_date": latest_share_event_date,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_account(db: Session, item: Account) -> dict:
    latest_snapshot_date = db.query(func.max(Position.snapshot_date)).filter(Position.account_id == item.id).scalar()
    position_count = db.query(func.count(Position.id)).filter(Position.account_id == item.id).scalar() or 0
    transaction_count = db.query(func.count(Transaction.id)).filter(Transaction.account_id == item.id).scalar() or 0
    latest_trade_date = db.query(func.max(Transaction.trade_date)).filter(Transaction.account_id == item.id).scalar()
    fund = db.query(Fund).filter(Fund.id == item.fund_id).first()
    client = db.query(Client).filter(Client.id == item.client_id).first() if item.client_id else None
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "fund_name": fund.name if fund else None,
        "client_id": item.client_id,
        "client_name": client.name if client else None,
        "broker": item.broker,
        "account_no": item.account_no,
        "position_count": int(position_count),
        "transaction_count": int(transaction_count),
        "latest_snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
        "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
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


def _serialize_fee(item: FeeRecord) -> dict:
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "fee_date": item.fee_date.isoformat(),
        "gross_return": _decimal(item.gross_return),
        "fee_rate": _decimal(item.fee_rate),
        "fee_amount_usd": _decimal(item.fee_amount_usd),
        "nav_start": _decimal(item.nav_start),
        "nav_end_before_fee": _decimal(item.nav_end_before_fee),
        "annual_return_pct": _decimal(item.annual_return_pct),
        "excess_return_pct": _decimal(item.excess_return_pct),
        "fee_base_usd": _decimal(item.fee_base_usd),
        "nav_after_fee": _decimal(item.nav_after_fee),
        "applied_date": item.applied_date.isoformat() if item.applied_date else None,
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


def _serialize_auth_user(item: Optional[AuthUser]) -> Optional[dict]:
    if item is None:
        return None
    return {
        "id": item.id,
        "username": item.username,
        "role": item.role,
        "permissions": list(permissions_for_role(item.role)),
        "client_scope_id": item.client_scope_id,
        "display_name": item.display_name,
        "is_active": item.is_active,
        "last_login_at": _iso(item.last_login_at),
        "password_changed_at": _iso(item.password_changed_at),
        "failed_login_attempts": item.failed_login_attempts,
        "locked_until": _iso(item.locked_until),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_auth_session(session) -> dict:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "csrf_token": session.csrf_token,
        "token_type": "bearer",
        "expires_at": session.access_expires_at.isoformat(),
        "refresh_expires_at": session.refresh_expires_at.isoformat(),
        "user": _serialize_auth_user(session.user),
    }


def _set_auth_cookies(response: Response, session) -> None:
    if not settings.auth_cookie_enabled:
        return
    common = {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        key=settings.auth_access_cookie_name,
        value=session.access_token,
        httponly=True,
        max_age=max(settings.auth_access_token_ttl_minutes * 60, 0),
        **common,
    )
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=session.refresh_token,
        httponly=True,
        max_age=max(settings.auth_refresh_token_ttl_days * 24 * 60 * 60, 0),
        **common,
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=session.csrf_token,
        httponly=False,
        max_age=max(settings.auth_refresh_token_ttl_days * 24 * 60 * 60, 0),
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    for cookie_name in (settings.auth_access_cookie_name, settings.auth_refresh_cookie_name, settings.auth_csrf_cookie_name):
        response.delete_cookie(cookie_name, path="/")


def _resolve_period(period_type: str, period_value: str) -> tuple[date, date]:
    period_type = period_type.lower()
    try:
        if period_type == "month":
            year_text, month_text = period_value.split("-")
            year = int(year_text)
            month = int(month_text)
            end_day = monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, end_day)

        if period_type == "quarter":
            year_text, quarter_text = period_value.split("-Q")
            year = int(year_text)
            quarter = int(quarter_text)
            if quarter not in {1, 2, 3, 4}:
                raise HTTPException(status_code=400, detail="quarter must be between 1 and 4")
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            end_day = monthrange(year, end_month)[1]
            return date(year, start_month, 1), date(year, end_month, end_day)

        if period_type == "year":
            year = int(period_value)
            return date(year, 1, 1), date(year, 12, 31)

        raise HTTPException(status_code=400, detail="period_type must be month, quarter, or year")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid period_value '{period_value}' for period_type '{period_type}'")


def _decimal(value):
    if value is None:
        return None
    return float(Decimal(str(value)))


def _iso(value):
    return value.isoformat() if value else None


def _aggregate_report_dimension(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        bucket_key = str(row.get(key))
        current = buckets.setdefault(bucket_key, {
            "key": row.get(key),
            "share_tx_count": 0,
            "subscription_amount_usd": 0.0,
            "redemption_amount_usd": 0.0,
            "net_share_flow_usd": 0.0,
            "shares_delta": 0.0,
            "latest_tx_date": row.get("tx_date"),
        })
        current["share_tx_count"] += 1
        amount = float(row.get("amount_usd") or 0)
        shares = float(row.get("shares") or 0)
        if row.get("tx_type") == "subscribe":
            current["subscription_amount_usd"] += amount
            current["shares_delta"] += shares
        elif row.get("tx_type") == "redeem":
            current["redemption_amount_usd"] += amount
            current["shares_delta"] -= shares
        current["net_share_flow_usd"] = current["subscription_amount_usd"] - current["redemption_amount_usd"]
        if row.get("tx_date") and (current["latest_tx_date"] is None or row["tx_date"] > current["latest_tx_date"]):
            current["latest_tx_date"] = row["tx_date"]
    return sorted(buckets.values(), key=lambda item: (-item["net_share_flow_usd"], str(item["key"])))


def _aggregate_transaction_assets(rows: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        asset_code = row.get("asset_code")
        current = buckets.setdefault(asset_code, {
            "asset_code": asset_code,
            "transaction_count": 0,
            "gross_notional_estimate": 0.0,
            "latest_trade_date": row.get("trade_date"),
        })
        current["transaction_count"] += 1
        current["gross_notional_estimate"] += abs(float(row.get("quantity") or 0) * float(row.get("price") or 0))
        if row.get("trade_date") and (current["latest_trade_date"] is None or row["trade_date"] > current["latest_trade_date"]):
            current["latest_trade_date"] = row["trade_date"]
    return sorted(buckets.values(), key=lambda item: (-item["transaction_count"], item["asset_code"] or ""))


def _aggregate_nav_by_fund(rows: list[dict]) -> list[dict]:
    counts: dict[int, int] = {}
    latest_rows: dict[int, dict] = {}
    for row in rows:
        fund_id = row.get("fund_id")
        counts[fund_id] = counts.get(fund_id, 0) + 1
        current = latest_rows.get(fund_id)
        if current is None or row.get("nav_date", "") > current.get("latest_nav_date", ""):
            latest_rows[fund_id] = {
                "fund_id": fund_id,
                "latest_nav_date": row.get("nav_date"),
                "latest_nav_per_share": row.get("nav_per_share"),
                "latest_total_assets_usd": row.get("total_assets_usd"),
            }
    return [
        {**latest_rows[fund_id], "record_count": counts[fund_id]}
        for fund_id in sorted(latest_rows.keys())
    ]


def _aggregate_share_flow_series(rows: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        tx_date = row.get("tx_date")
        current = buckets.setdefault(tx_date, {
            "date": tx_date,
            "subscription_amount_usd": 0.0,
            "redemption_amount_usd": 0.0,
            "net_share_flow_usd": 0.0,
            "share_tx_count": 0,
        })
        current["share_tx_count"] += 1
        amount = float(row.get("amount_usd") or 0)
        if row.get("tx_type") == "subscribe":
            current["subscription_amount_usd"] += amount
        elif row.get("tx_type") == "redeem":
            current["redemption_amount_usd"] += amount
        current["net_share_flow_usd"] = current["subscription_amount_usd"] - current["redemption_amount_usd"]
    return [buckets[key] for key in sorted(buckets.keys())]


def _aggregate_nav_series(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": row.get("nav_date"),
            "fund_id": row.get("fund_id"),
            "nav_per_share": row.get("nav_per_share"),
            "total_assets_usd": row.get("total_assets_usd"),
        }
        for row in sorted(rows, key=lambda item: (item.get("nav_date", ""), item.get("fund_id") or 0))
    ]
