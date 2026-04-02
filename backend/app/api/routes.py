from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date

logger = logging.getLogger(__name__)
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Account, AssetPrice, AuthUser, CashPosition, ExchangeRate, NAVRecord, Position, Transaction
from app.schemas.common import (
    AuthPasswordChangeRequest,
    AuthPasswordResetRequest,
    AuthUserCreateRequest,
    AuthUserUpdateRequest,
    AccountCreateRequest,
    AccountUpdateRequest,
    NavCalcRequest,
    NavRebuildRequest,
    PriceManualRequest,
    PriceFetchRequest,
    RateFetchRequest,
    RateManualRequest,
    TransactionCreateRequest,
    TransactionUpdateRequest,
)
from app.services.audit import list_audit_logs, record_audit
from app.services.auth import (
    Actor,
    admin_reset_password,
    change_password,
    create_auth_user,
    get_actor,
    list_auth_users,
    login_with_password,
    refresh_access_token,
    require_permissions,
    revoke_session,
    unlock_user,
    update_auth_user,
    permissions_for_role,
)
from app.services.cash_ledger import get_all_cash_balances, get_cash_balance, get_cash_history
from app.services.exchange_rate import fetch_and_save_rates, save_rate_manual, save_rates_csv
from app.services.import_service import confirm_batch, get_batch, list_batches, reset_batch, serialize_batch, upload_csv
from app.services.nav_engine import calc_nav, check_nav_rates, list_nav, rebuild_nav_batch
from app.services.price_service import fetch_and_save_prices, save_price_manual, save_prices_csv
from app.services.scheduler import SCHEDULER_JOB_FX_WEEKLY, list_job_runs, run_weekly_fx_job

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


@router.get("/auth/users")
def list_users(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "auth.manage")
    return [_serialize_auth_user(u) for u in list_auth_users(db)]


@router.post("/auth/users", status_code=201)
def create_user(req: AuthUserCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "auth.manage")
    user = create_auth_user(
        db,
        username=req.username,
        password=req.password,
        role=req.role,
        display_name=req.display_name,
        is_active=req.is_active,
    )
    return _serialize_auth_user(user)


@router.patch("/auth/users/{user_id}")
def update_user(user_id: int, req: AuthUserUpdateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "auth.manage")
    user = update_auth_user(
        db,
        user_id=user_id,
        role=req.role,
        display_name=req.display_name,
        is_active=req.is_active,
    )
    return _serialize_auth_user(user)


@router.post("/auth/users/{user_id}/reset-password")
def reset_user_password(user_id: int, req: AuthPasswordResetRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "auth.manage")
    user = admin_reset_password(db, user_id=user_id, new_password=req.new_password)
    return _serialize_auth_user(user)


@router.post("/auth/users/{user_id}/unlock")
def unlock_user_route(user_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "auth.manage")
    return unlock_user(db, user_id)


@router.patch("/auth/me/password")
def change_my_password(req: AuthPasswordChangeRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    user = change_password(db, actor=actor, current_password=req.current_password, new_password=req.new_password)
    return _serialize_auth_user(user)


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


@router.post("/rates/csv")
async def import_rates_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Bulk-import FX rates from CSV (columns: date,from_currency,to_currency,rate)."""
    require_permissions(actor, "rates.write")
    content = await file.read()
    rows = save_rates_csv(db, content)
    record_audit(db, actor, action="rate.csv_import", entity_type="exchange_rate", entity_id="batch", detail={"count": len(rows)})
    return {"imported": len(rows)}


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


@router.post("/price/manual")
def upsert_price_manual(req: PriceManualRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Manually upsert a single asset price."""
    require_permissions(actor, "price.write")
    row = save_price_manual(db, req.asset_code, float(req.price_usd), req.snapshot_date)
    record_audit(db, actor, action="price.manual", entity_type="asset_price", entity_id=str(row.id),
                 detail={"asset_code": req.asset_code, "price_usd": float(req.price_usd), "snapshot_date": req.snapshot_date.isoformat()})
    return _serialize_price(row)


@router.post("/price/csv")
async def import_prices_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Bulk-import asset prices from CSV (columns: asset_code,price_usd,price_date)."""
    require_permissions(actor, "price.write")
    content = await file.read()
    rows = save_prices_csv(db, content)
    record_audit(db, actor, action="price.csv_import", entity_type="asset_price", entity_id="batch", detail={"count": len(rows)})
    return {"imported": len(rows)}


@router.get("/nav/check-rates")
def nav_check_rates(nav_date: date, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Pre-flight check: return which FX rates are missing for a NAV calculation date."""
    require_permissions(actor, "nav.read")
    return check_nav_rates(db, nav_date)


@router.post("/nav/calc")
def run_nav(req: NavCalcRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    try:
        row = calc_nav(db, req.nav_date, force=req.force)
        record_audit(
            db,
            actor,
            action="nav.calc",
            entity_type="nav_record",
            entity_id=str(row.id),
            detail={"nav_date": req.nav_date.isoformat()},
        )
        return _serialize_nav(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nav")
def get_nav_records(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.read")
    return [_serialize_nav(item) for item in list_nav(db)]


@router.delete("/nav/{nav_id}", status_code=204)
def delete_nav(nav_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    item = db.query(NAVRecord).filter(NAVRecord.id == nav_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="NAV record not found.")
    nav_date = item.nav_date.isoformat()
    from app.models import AssetSnapshot as _AssetSnapshot
    db.query(_AssetSnapshot).filter(_AssetSnapshot.nav_record_id == nav_id).delete()
    db.delete(item)
    db.commit()
    record_audit(db, actor, action="nav.delete", entity_type="nav_record", entity_id=str(nav_id), detail={"nav_date": nav_date})


@router.get("/import")
def get_import_batches(account_id: Optional[int] = None, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.read")
    batches = list_batches(db)
    if account_id is not None:
        batches = [b for b in batches if b.account_id == account_id]
    return [serialize_batch(batch) for batch in batches]


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
    force: bool = Form(False),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "import.write")
    try:
        payload = await file.read()
        batch = upload_csv(db, source=source, filename=file.filename or "upload.csv", account_id=account_id, content=payload, force=force)
        record_audit(
            db,
            actor,
            action="import.upload",
            entity_type="import_batch",
            entity_id=str(batch.id),
            detail={"source": source, "account_id": account_id, "filename": file.filename or "upload.csv", "status": batch.status, "force": force},
        )
        return serialize_batch(batch)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("duplicate_file:"):
            existing_id = int(msg.split(":")[1])
            raise HTTPException(status_code=409, detail={"duplicate": True, "existing_batch_id": existing_id, "message": "Duplicate file detected"})
        raise HTTPException(status_code=400, detail=msg)


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


@router.post("/import/{batch_id}/reset")
def reset_import_batch(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.write")
    try:
        batch = reset_batch(db, batch_id)
        record_audit(
            db, actor, action="import.reset",
            entity_type="import_batch", entity_id=str(batch.id),
            detail={"account_id": batch.account_id},
        )
        return serialize_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nav/rebuild-batch")
def rebuild_nav_batch_endpoint(req: NavRebuildRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    results = rebuild_nav_batch(db, req.start_date, req.end_date, req.frequency, force=req.force)
    return {"results": results}


# ── V4.3 Cash Ledger API (read-only, calculated from transactions) ────────

@router.get("/cash/balance")
def get_cash_balance_all(
    account_id: int,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return all currency balances for an account, calculated from transactions."""
    require_permissions(actor, "nav.read")
    as_of = as_of_date or date.today()
    balances = get_all_cash_balances(account_id, as_of, db)
    return {
        "account_id": account_id,
        "as_of_date": as_of.isoformat(),
        "balances": {k: float(v) for k, v in balances.items()},
    }


@router.get("/cash/balance/{currency}")
def get_cash_balance_currency(
    currency: str,
    account_id: int,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return single-currency balance for an account."""
    require_permissions(actor, "nav.read")
    as_of = as_of_date or date.today()
    bal = get_cash_balance(account_id, currency.upper(), as_of, db)
    return {
        "account_id": account_id,
        "currency": currency.upper(),
        "as_of_date": as_of.isoformat(),
        "balance": float(bal),
    }


@router.get("/cash/flow")
def get_cash_flow(
    account_id: int,
    currency: str = "USD",
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return chronological cash ledger entries with running balance."""
    require_permissions(actor, "nav.read")
    events = get_cash_history(account_id, currency.upper(), db, limit=limit)
    return [
        {
            "tx_id":        e.tx_id,
            "trade_date":   e.trade_date.isoformat(),
            "settle_date":  e.settle_date.isoformat() if e.settle_date else None,
            "tx_category":  e.tx_category,
            "tx_type":      e.tx_type,
            "description":  e.description,
            "currency":     e.currency,
            "delta":        float(e.delta),
            "balance_after":float(e.balance_after),
        }
        for e in events
    ]


@router.get("/cash/flow/export")
def export_cash_flow(
    account_id: int,
    currency: str = "USD",
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Download cash flow as CSV."""
    import io as _io
    import csv as _csv
    require_permissions(actor, "nav.read")
    events = get_cash_history(account_id, currency.upper(), db, limit=10000)
    # Events returned latest-first; reverse for chronological CSV
    events_chrono = list(reversed(events))
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["date", "settle_date", "tx_category", "tx_type", "description", "asset_code", "delta", "balance"])
    for e in events_chrono:
        writer.writerow([
            e.trade_date.isoformat(),
            e.settle_date.isoformat() if e.settle_date else "",
            e.tx_category,
            e.tx_type,
            e.description or "",
            "",
            float(e.delta),
            float(e.balance_after),
        ])
    content = buf.getvalue().encode("utf-8")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cash_flow_{account_id}_{currency}.csv"},
    )


# ── Duplicate detection ───────────────────────────────────────────────────

@router.post("/import/check-duplicate")
def check_import_duplicate(
    req: dict,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Check if a transaction already exists (for import preview dedup)."""
    require_permissions(actor, "import.write")
    account_id = req.get("account_id")
    tx_category = (req.get("tx_category") or "").upper()
    existing = None

    if tx_category == "TRADE":
        q = db.query(Transaction).filter(
            Transaction.account_id == account_id,
            Transaction.trade_date == req.get("trade_date"),
            Transaction.asset_code == req.get("asset_code"),
        )
        if req.get("quantity") is not None:
            q = q.filter(Transaction.quantity == req["quantity"])
        if req.get("price") is not None:
            q = q.filter(Transaction.price == req["price"])
        existing = q.first()
    else:
        q = db.query(Transaction).filter(
            Transaction.account_id == account_id,
            Transaction.trade_date == req.get("trade_date"),
            Transaction.tx_type == req.get("tx_type"),
            Transaction.currency == req.get("currency"),
        )
        if req.get("gross_amount") is not None:
            q = q.filter(Transaction.gross_amount == req["gross_amount"])
        existing = q.first()

    return {
        "is_duplicate": existing is not None,
        "existing_tx_id": existing.id if existing else None,
    }


# ── Legacy /cash list (read-only) ─────────────────────────────────────────

@router.get("/cash")
def list_cash_positions(
    account_id: Optional[int] = None,
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "nav.read")
    query = db.query(CashPosition)
    if account_id:
        query = query.filter(CashPosition.account_id == account_id)
    if snapshot_date:
        query = query.filter(CashPosition.snapshot_date == snapshot_date)
    rows = query.order_by(CashPosition.snapshot_date.desc(), CashPosition.id.desc()).all()
    return [_serialize_cash(r) for r in rows]


@router.get("/account")
def list_accounts(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    holder: Optional[str] = None,
    broker: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Account)
    if holder:
        query = query.filter(Account.holder_name.ilike(f"%{holder.strip()}%"))
    if broker:
        query = query.filter(Account.broker.ilike(f"%{broker.strip()}%"))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Account.account_no.ilike(like)) | (Account.broker.ilike(like)) | (Account.holder_name.ilike(like)))
    return _paginate(query.order_by(Account.id.asc()), page, size, lambda item: _serialize_account(db, item))


@router.get("/account/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.read")
    item = db.query(Account).filter(Account.id == account_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Account not found.")
    return _serialize_account(db, item)


@router.post("/account")
def create_account(req: AccountCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.write")
    account = Account(
        holder_name=req.holder_name,
        broker=req.broker,
        account_no=req.account_no,
        # V4.1: IB margin account fields
        base_currency=req.base_currency or "USD",
        account_capabilities=req.account_capabilities,
        is_margin=req.is_margin or False,
        master_account_no=req.master_account_no,
        ib_account_no=req.ib_account_no,
    )
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
    if 'holder_name' in req.model_fields_set:
        item.holder_name = req.holder_name
    if req.broker is not None:
        item.broker = req.broker
    if req.account_no is not None:
        item.account_no = req.account_no
    # V4.1: IB margin account fields
    if req.base_currency is not None:
        item.base_currency = req.base_currency
    if req.account_capabilities is not None:
        item.account_capabilities = req.account_capabilities
    if req.is_margin is not None:
        item.is_margin = req.is_margin
    if req.master_account_no is not None:
        item.master_account_no = req.master_account_no
    if req.ib_account_no is not None:
        item.ib_account_no = req.ib_account_no
    db.commit()
    db.refresh(item)
    record_audit(db, actor, action="account.update", entity_type="account", entity_id=str(item.id), detail={"account_no": item.account_no})
    return _serialize_account(db, item)


@router.get("/account/{account_id}/nav-breakdown")
def get_account_nav_breakdown(
    account_id: int,
    as_of_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """V4.1: Full NAV breakdown for an IB multi-currency margin account."""
    require_permissions(actor, "accounts.read")
    item = db.query(Account).filter(Account.id == account_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Account not found.")
    from app.services.nav_breakdown import get_nav_breakdown
    from datetime import date as _date
    effective_date = as_of_date or _date.today()
    return get_nav_breakdown(account_id, effective_date, db)


@router.get("/position")
def list_positions(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    account_id: Optional[int] = None,
    snapshot_date: Optional[date] = None,
    asset_code: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Position)
    if account_id is not None:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            query = query.filter(Position.account_id == account_id)
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
    return _serialize_position(item)


@router.get("/transaction")
def list_transactions(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    account_id: Optional[int] = None,
    trade_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tx_category: Optional[str] = None,
    tx_type: Optional[str] = None,
    asset_code: Optional[str] = None,
    source: Optional[str] = None,
    import_batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Transaction)
    if account_id is not None:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            query = query.filter(Transaction.account_id == account_id)
    if trade_date is not None:
        query = query.filter(Transaction.trade_date == trade_date)
    if date_from is not None:
        query = query.filter(Transaction.trade_date >= date_from)
    if date_to is not None:
        query = query.filter(Transaction.trade_date <= date_to)
    if tx_category is not None:
        # Support legacy aliases: EQUITY->TRADE
        cats = [tx_category.upper()]
        if tx_category.upper() == "TRADE":
            cats.append("EQUITY")
        elif tx_category.upper() == "EQUITY":
            cats.append("TRADE")
        query = query.filter(Transaction.tx_category.in_(cats))
    if tx_type is not None:
        query = query.filter(Transaction.tx_type == tx_type.lower())
    if asset_code is not None:
        query = query.filter(Transaction.asset_code.ilike(f"%{asset_code}%"))
    if source is not None:
        query = query.filter(Transaction.source == source)
    if import_batch_id is not None:
        query = query.filter(Transaction.import_batch_id == import_batch_id)
    return _paginate(query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()), page, size, _serialize_transaction)


@router.get("/transaction/{transaction_id}")
def get_transaction(transaction_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "accounts.read")
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return _serialize_transaction(item)


@router.post("/transaction")
def create_transaction(req: TransactionCreateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """V4.2: Manual transaction entry for all transaction types."""
    require_permissions(actor, "accounts.write")
    account = db.query(Account).filter(Account.id == req.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    tx = Transaction(
        account_id=req.account_id,
        tx_category=req.tx_category.upper(),
        tx_type=req.tx_type.lower(),
        trade_date=req.trade_date,
        settle_date=req.settle_date,
        currency=req.currency.upper(),
        description=req.description,
        source=req.source or "manual",
        # Amount fields
        gross_amount=req.gross_amount,
        commission=req.commission,
        transaction_fee=req.transaction_fee,
        other_fee=req.other_fee,
        amount=req.amount,
        fee=req.fee or 0,
        # TRADE fields
        asset_code=req.asset_code.upper() if req.asset_code else None,
        asset_name=req.asset_name,
        asset_type=req.asset_type,
        exchange=req.exchange,
        isin=req.isin,
        quantity=req.quantity,
        price=req.price,
        realized_pnl=req.realized_pnl,
        cost_basis=req.cost_basis,
        # Option fields
        option_underlying=req.option_underlying,
        option_expiry=req.option_expiry,
        option_strike=req.option_strike,
        option_type=req.option_type,
        option_multiplier=req.option_multiplier,
        # FX fields
        fx_from_currency=req.fx_from_currency,
        fx_from_amount=req.fx_from_amount,
        fx_to_currency=req.fx_to_currency,
        fx_to_amount=req.fx_to_amount,
        fx_rate=req.fx_rate,
        # Lending fields
        lending_asset_code=req.lending_asset_code,
        lending_quantity=req.lending_quantity,
        lending_rate_pct=req.lending_rate_pct,
        collateral_amount=req.collateral_amount,
        # Accrual fields
        accrual_type=req.accrual_type,
        accrual_period_start=req.accrual_period_start,
        accrual_period_end=req.accrual_period_end,
        is_accrual_reversal=req.is_accrual_reversal or False,
        # Corporate fields
        corporate_ratio=req.corporate_ratio,
        corporate_new_code=req.corporate_new_code,
        # Internal transfer
        counterparty_account=req.counterparty_account,
        tx_subtype=req.tx_subtype,
        created_by=actor.user_id if hasattr(actor, "user_id") else None,
        updated_by=actor.user_id if hasattr(actor, "user_id") else None,
    )
    db.add(tx)
    db.flush()

    # Trigger position recalculation for TRADE transactions
    if tx.tx_category.upper() in ("TRADE", "EQUITY") and tx.asset_code:
        try:
            from app.services.position_calculator import recalculate_position
            recalculate_position(req.account_id, tx.asset_code, db)
        except Exception as exc:
            logger.warning(f"position recalc failed after create: {exc}")

    db.commit()
    db.refresh(tx)
    return _serialize_transaction(tx)


@router.patch("/transaction/{transaction_id}")
def update_transaction(transaction_id: int, req: TransactionUpdateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """V4.2: Edit an existing transaction (admin or ops)."""
    require_permissions(actor, "accounts.write")
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    old_asset = tx.asset_code
    fields = req.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if field == "tx_category" and value:
            value = value.upper()
        elif field == "tx_type" and value:
            value = value.lower()
        elif field == "currency" and value:
            value = value.upper()
        elif field == "asset_code" and value:
            value = value.upper()
        setattr(tx, field, value)

    if hasattr(actor, "user_id"):
        tx.updated_by = actor.user_id

    db.flush()

    # Trigger position recalculation if asset or category changed
    affected_assets = {a for a in [old_asset, tx.asset_code] if a}
    for asset in affected_assets:
        if tx.tx_category.upper() in ("TRADE", "EQUITY"):
            try:
                from app.services.position_calculator import recalculate_position
                recalculate_position(tx.account_id, asset, db)
            except Exception as exc:
                logger.warning(f"position recalc failed after update: {exc}")

    db.commit()
    db.refresh(tx)
    return _serialize_transaction(tx)


@router.delete("/transaction/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """V4.2: Delete a transaction (admin only) with protection checks."""
    require_permissions(actor, "admin")
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    # Protection 1: CSV-imported records must be deleted via batch reset
    if tx.source == "csv_import" and tx.import_batch_id:
        raise HTTPException(
            status_code=400,
            detail=f"CSV-imported records must be deleted via batch reset, not individually. (batch #{tx.import_batch_id})",
        )

    account_id = tx.account_id
    asset_code = tx.asset_code
    tx_category = tx.tx_category

    db.delete(tx)
    db.flush()

    # Recalculate position if TRADE
    if tx_category and tx_category.upper() in ("TRADE", "EQUITY") and asset_code:
        try:
            from app.services.position_calculator import recalculate_position
            recalculate_position(account_id, asset_code, db)
        except Exception as exc:
            logger.warning(f"position recalc failed after delete: {exc}")

    db.commit()
    return {"status": "deleted", "id": transaction_id}


@router.post("/transaction/fx")
def create_fx_transaction(req: dict, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Record a manual FX (foreign exchange) trade."""
    require_permissions(actor, "accounts.write")
    from app.services.fx_service import record_fx_trade
    from decimal import Decimal as _Dec

    account_id = req.get("account_id")
    if not account_id:
        raise HTTPException(status_code=422, detail="account_id required.")
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    try:
        trade_date_str = req["trade_date"]
        trade_date_obj = date.fromisoformat(trade_date_str)
        tx = record_fx_trade(
            account_id=account_id,
            trade_date=trade_date_obj,
            from_currency=req["fx_from_currency"],
            from_amount=_Dec(str(req["fx_from_amount"])),
            to_currency=req["fx_to_currency"],
            to_amount=_Dec(str(req["fx_to_amount"])),
            fee=_Dec(str(req.get("fee", "0"))),
            fee_currency=req.get("fee_currency"),
            description=req.get("description"),
            source="manual",
            db=db,
        )
        db.commit()
        db.refresh(tx)
        return _serialize_transaction(tx)
    except (KeyError, Exception) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/accounts/{account_id}/cash-ledger")
def get_cash_ledger(
    account_id: int,
    currency: str = Query(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return cash ledger history for a specific account+currency."""
    require_permissions(actor, "accounts.read")
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    from app.services.cash_ledger import get_cash_history
    events = get_cash_history(account_id, currency, db)
    return {
        "account_id": account_id,
        "currency": currency.upper(),
        "events": [
            {
                "tx_id": e.tx_id,
                "trade_date": e.trade_date.isoformat(),
                "settle_date": e.settle_date.isoformat() if e.settle_date else None,
                "tx_category": e.tx_category,
                "tx_type": e.tx_type,
                "description": e.description,
                "delta": float(e.delta),
                "balance_after": float(e.balance_after),
            }
            for e in events
        ],
    }


@router.get("/accounts/{account_id}/cash-balances")
def get_cash_balances(
    account_id: int,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return all currency balances for account, computed from Transaction events."""
    require_permissions(actor, "accounts.read")
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    from app.services.cash_ledger import get_all_cash_balances
    from datetime import date as _date
    eval_date = as_of_date or _date.today()
    balances = get_all_cash_balances(account_id, eval_date, db)
    return {
        "account_id": account_id,
        "as_of_date": eval_date.isoformat(),
        "balances": {ccy: float(amt) for ccy, amt in sorted(balances.items())},
    }


@router.get("/accounts/{account_id}/fx-summary")
def get_fx_summary_endpoint(
    account_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Return FX trade summary and P&L for an account."""
    require_permissions(actor, "accounts.read")
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    from app.services.fx_service import get_fx_summary
    summaries = get_fx_summary(account_id, db)
    return {
        "account_id": account_id,
        "fx_trades": [
            {
                "from_currency": s.from_currency,
                "to_currency": s.to_currency,
                "total_from": float(s.total_from),
                "total_to": float(s.total_to),
                "avg_rate": float(s.avg_rate),
                "total_fee_usd": float(s.total_fee_usd),
                "realized_pnl_usd": float(s.realized_pnl_usd),
            }
            for s in summaries
        ],
    }


@router.get("/reports/overview")
def get_reports_overview(
    period_type: str = Query("quarter"),
    period_value: str = Query(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "reports.read")
    start_date, end_date = _resolve_period(period_type, period_value)

    nav_query = db.query(NAVRecord).filter(and_(NAVRecord.nav_date >= start_date, NAVRecord.nav_date <= end_date))
    nav_rows = [_serialize_nav(item) for item in nav_query.order_by(NAVRecord.nav_date.desc(), NAVRecord.id.desc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    transaction_rows = [_serialize_transaction(item) for item in transaction_query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()).all()]

    return {
        "filters": {
            "period_type": period_type,
            "period_value": period_value,
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "viewer_role": actor.role,
        },
        "summary": {
            "nav_record_count": len(nav_rows),
            "transaction_count": len(transaction_rows),
            "latest_nav_date": nav_rows[0]["nav_date"] if nav_rows else None,
        },
        "nav_records": nav_rows,
        "transactions": transaction_rows,
        "breakdowns": {
            "transactions_by_asset": _aggregate_transaction_assets(transaction_rows),
        },
    }


@router.get("/reports/export")
def export_reports(
    period_type: str = Query("quarter"),
    period_value: str = Query(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "reports.read")
    import io
    import csv
    from starlette.responses import StreamingResponse
    start_date, end_date = _resolve_period(period_type, period_value)

    nav_query = db.query(NAVRecord).filter(and_(NAVRecord.nav_date >= start_date, NAVRecord.nav_date <= end_date))
    nav_rows = [_serialize_nav(item) for item in nav_query.order_by(NAVRecord.nav_date.asc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    transaction_rows = [_serialize_transaction(item) for item in transaction_query.order_by(Transaction.trade_date.asc()).all()]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["# NAV Records"])
    writer.writerow(["nav_date", "total_assets_usd"])
    for row in nav_rows:
        writer.writerow([row["nav_date"], row["total_assets_usd"]])

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
    return list_audit_logs(db, limit=limit, action=action)


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


def _paginate(query, page: int, size: int, serializer):
    total = query.order_by(None).count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {
        "items": [serializer(item) for item in items],
        "pagination": {"page": page, "size": size, "total": total},
    }


def _serialize_account(db: Session, item: Account) -> dict:
    latest_snapshot_date = db.query(func.max(Position.snapshot_date)).filter(Position.account_id == item.id).scalar()
    position_count = db.query(func.count(Position.id)).filter(Position.account_id == item.id).scalar() or 0
    transaction_count = db.query(func.count(Transaction.id)).filter(Transaction.account_id == item.id).scalar() or 0
    latest_trade_date = db.query(func.max(Transaction.trade_date)).filter(Transaction.account_id == item.id).scalar()

    # Snapshot cost-basis value (quantity x average_cost) for latest snapshot date
    latest_snapshot_value_usd = None
    if latest_snapshot_date:
        snap_positions = db.query(Position).filter(
            Position.account_id == item.id,
            Position.snapshot_date == latest_snapshot_date,
        ).all()
        if snap_positions:
            latest_snapshot_value_usd = sum(
                float(p.quantity) * float(p.average_cost or 0)
                for p in snap_positions
            )

    return {
        "id": item.id,
        "holder_name": item.holder_name,
        "broker": item.broker,
        "account_no": item.account_no,
        "position_count": int(position_count),
        "transaction_count": int(transaction_count),
        "latest_snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
        "latest_snapshot_value_usd": latest_snapshot_value_usd,
        "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
        # V4.1: IB multi-currency margin account fields
        "base_currency": getattr(item, "base_currency", None) or "USD",
        "account_capabilities": getattr(item, "account_capabilities", None),
        "is_margin": getattr(item, "is_margin", None) or False,
        "master_account_no": getattr(item, "master_account_no", None),
        "ib_account_no": getattr(item, "ib_account_no", None),
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
    d = {
        "id": item.id,
        "account_id": item.account_id,
        "tx_category": getattr(item, "tx_category", None) or "EQUITY",
        "tx_type": item.tx_type,
        "source": getattr(item, "source", None) or "manual",
        "trade_date": item.trade_date.isoformat(),
        "settle_date": item.settle_date.isoformat() if getattr(item, "settle_date", None) else None,
        "currency": item.currency,
        "amount": _decimal(getattr(item, "amount", None)),
        "fee": _decimal(item.fee),
        "description": getattr(item, "description", None),
        # EQUITY fields
        "asset_code": item.asset_code,
        "asset_name": getattr(item, "asset_name", None),
        "asset_type": getattr(item, "asset_type", None),
        "quantity": _decimal(item.quantity),
        "price": _decimal(item.price),
        "realized_pnl": _decimal(getattr(item, "realized_pnl", None)),
        # Option fields
        "option_underlying": getattr(item, "option_underlying", None),
        "option_expiry": item.option_expiry.isoformat() if getattr(item, "option_expiry", None) else None,
        "option_strike": _decimal(getattr(item, "option_strike", None)),
        "option_type": getattr(item, "option_type", None),
        "option_multiplier": getattr(item, "option_multiplier", None),
        # FX fields
        "fx_from_currency": getattr(item, "fx_from_currency", None),
        "fx_from_amount": _decimal(getattr(item, "fx_from_amount", None)),
        "fx_to_currency": getattr(item, "fx_to_currency", None),
        "fx_to_amount": _decimal(getattr(item, "fx_to_amount", None)),
        "fx_rate": _decimal(getattr(item, "fx_rate", None)),
        "fx_pnl": _decimal(getattr(item, "fx_pnl", None)),
        # Corporate action fields
        "corporate_ratio": _decimal(getattr(item, "corporate_ratio", None)),
        "corporate_ref_code": getattr(item, "corporate_ref_code", None),
        # V4.1: subtype + fee decomposition
        "tx_subtype": getattr(item, "tx_subtype", None),
        "gross_amount": _decimal(getattr(item, "gross_amount", None)),
        "commission": _decimal(getattr(item, "commission", None)),
        "transaction_fee": _decimal(getattr(item, "transaction_fee", None)),
        "other_fee": _decimal(getattr(item, "other_fee", None)),
        # V4.1: asset metadata
        "isin": getattr(item, "isin", None),
        "exchange": getattr(item, "exchange", None),
        "multiplier": getattr(item, "multiplier", None),
        "close_price": _decimal(getattr(item, "close_price", None)),
        "cost_basis": _decimal(getattr(item, "cost_basis", None)),
        # V4.1: securities lending
        "lending_counterparty": getattr(item, "lending_counterparty", None),
        "lending_rate": _decimal(getattr(item, "lending_rate", None)),
        "collateral_amount": _decimal(getattr(item, "collateral_amount", None)),
        # V4.1: accruals
        "accrual_type": getattr(item, "accrual_type", None),
        "accrual_period_start": item.accrual_period_start.isoformat() if getattr(item, "accrual_period_start", None) else None,
        "accrual_period_end": item.accrual_period_end.isoformat() if getattr(item, "accrual_period_end", None) else None,
        "accrual_reversal_id": getattr(item, "accrual_reversal_id", None),
        # V4.1: internal transfer
        "counterparty_account": getattr(item, "counterparty_account", None),
        # V4.2: Securities lending detail
        "lending_asset_code": getattr(item, "lending_asset_code", None),
        "lending_quantity": _decimal(getattr(item, "lending_quantity", None)),
        "lending_rate_pct": _decimal(getattr(item, "lending_rate_pct", None)),
        # V4.2: Accrual reversal flag
        "is_accrual_reversal": getattr(item, "is_accrual_reversal", None),
        # V4.2: Corporate action new code
        "corporate_new_code": getattr(item, "corporate_new_code", None),
        # Metadata
        "import_batch_id": item.import_batch_id,
        "created_by": getattr(item, "created_by", None),
        "updated_by": getattr(item, "updated_by", None),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
    return d


def _serialize_nav(item) -> dict:
    return {
        "id": item.id,
        "nav_date": item.nav_date.isoformat(),
        "total_assets_usd": _decimal(item.total_assets_usd),
        "is_locked": item.is_locked,
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
        "source": getattr(item, "source", None),
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


def _serialize_cash(item: CashPosition) -> dict:
    return {
        "id": item.id,
        "account_id": item.account_id,
        "currency": item.currency,
        "amount": _decimal(item.amount),
        "snapshot_date": _iso(item.snapshot_date),
        "note": item.note,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
