from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date

logger = logging.getLogger(__name__)
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status, BackgroundTasks
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Account, AssetPrice, AuthUser, CashPosition, Client, ClientCapitalAccount, ExchangeRate, FeeRecord, Fund, NAVRecord, PdfImportBatch, Position, ShareRegister, ShareTransaction, Transaction
from app.schemas.common import (
    AuthPasswordChangeRequest,
    AuthPasswordResetRequest,
    AuthUserCreateRequest,
    AuthUserUpdateRequest,
    CashPositionUpsertRequest,
    ClientCreateRequest,
    ClientUpdateRequest,
    AccountCreateRequest,
    AccountUpdateRequest,
    DepositConfirmRequest,
    FeeCalcRequest,
    FundCreateRequest,
    FundUpdateRequest,
    NavCalcRequest,
    NavRebuildRequest,
    PdfImportConfirmRequest,
    PriceManualRequest,
    PriceFetchRequest,
    RateFetchRequest,
    RateManualRequest,
    SeedCapitalRequest,
    ShareRequest,
    TransactionCreateRequest,
    TransactionUpdateRequest,
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
    unlock_user,
    update_auth_user,
    permissions_for_role,
)
from app.services.exchange_rate import fetch_and_save_rates, save_rate_manual, save_rates_csv
from app.services.fee_service import calc_fee, list_fees
from app.services.import_service import confirm_batch, get_batch, list_batches, reset_batch, serialize_batch, upload_csv
from app.services.nav_engine import calc_nav, check_nav_rates, list_nav, rebuild_nav_batch
from app.services.pdf_parser_service import confirm_pdf_batch, serialize_pdf_batch
from app.services.pdf_validator_service import validate_parsed_result
from app.services.price_service import fetch_and_save_prices, save_price_manual, save_prices_csv
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
        client_scope_id=req.client_scope_id,
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
        client_scope_id=req.client_scope_id,
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
def nav_check_rates(fund_id: int, nav_date: date, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Pre-flight check: return which FX rates are missing for a NAV calculation date."""
    require_permissions(actor, "nav.read")
    return check_nav_rates(db, fund_id, nav_date)


@router.post("/nav/calc")
def run_nav(req: NavCalcRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    try:
        row = calc_nav(db, req.fund_id, req.nav_date, force=req.force)
        record_audit(
            db,
            actor,
            action="nav.calc",
            entity_type="nav_record",
            entity_id=str(row.id),
            detail={"fund_id": req.fund_id, "nav_date": req.nav_date.isoformat()},
        )
        return _serialize_nav(row, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nav")
def get_nav_records(fund_id: Optional[int] = None, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.read")
    if actor.role == ROLE_CLIENT_READONLY and fund_id is None:
        fund_ids = _client_fund_ids(db, actor.client_scope_id)
        return [_serialize_nav(item, db) for item in list_nav(db) if item.fund_id in fund_ids]
    return [_serialize_nav(item, db) for item in list_nav(db, fund_id=fund_id)]


@router.delete("/nav/{nav_id}", status_code=204)
def delete_nav(nav_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    item = db.query(NAVRecord).filter(NAVRecord.id == nav_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="NAV record not found.")
    fund_id = item.fund_id
    nav_date = item.nav_date.isoformat()
    from app.models import AssetSnapshot as _AssetSnapshot
    db.query(_AssetSnapshot).filter(_AssetSnapshot.nav_record_id == nav_id).delete()
    db.delete(item)
    db.commit()
    record_audit(db, actor, action="nav.delete", entity_type="nav_record", entity_id=str(nav_id), detail={"fund_id": fund_id, "nav_date": nav_date})


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


@router.patch("/share/transaction/{tx_id}")
def update_share_transaction(tx_id: int, req: dict, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "shares.write")
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can edit share transactions.")
    from app.models import ShareTransaction as _ShareTx
    tx = db.query(_ShareTx).filter(_ShareTx.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Share transaction not found.")
    allowed = {"tx_date", "tx_type", "amount_usd", "shares", "nav_at_date", "fund_id", "client_id"}
    for key, val in req.items():
        if key in allowed:
            setattr(tx, key, val)
    db.commit()
    db.refresh(tx)
    record_audit(db, actor, action="share_tx.update", entity_type="share_transaction", entity_id=str(tx.id), detail=req)
    return {
        "id": tx.id, "fund_id": tx.fund_id, "client_id": tx.client_id,
        "tx_date": tx.tx_date.isoformat(), "tx_type": tx.tx_type,
        "amount_usd": _decimal(tx.amount_usd), "shares": _decimal(tx.shares),
        "nav_at_date": _decimal(tx.nav_at_date),
    }


@router.delete("/share/transaction/{tx_id}", status_code=204)
def delete_share_transaction(tx_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "shares.write")
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete share transactions.")
    from app.models import ShareTransaction as _ShareTx
    tx = db.query(_ShareTx).filter(_ShareTx.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Share transaction not found.")
    record_audit(db, actor, action="share_tx.delete", entity_type="share_transaction", entity_id=str(tx.id),
                 detail={"fund_id": tx.fund_id, "tx_type": tx.tx_type, "amount_usd": str(tx.amount_usd), "shares": str(tx.shares)})
    db.delete(tx)
    db.commit()


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
            raise HTTPException(status_code=409, detail={"duplicate": True, "existing_batch_id": existing_id, "message": "检测到重复文件"})
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


@router.get("/import/{batch_id}/pending-deposits")
def get_pending_deposits(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.read")
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    return batch.pending_deposit_rows


@router.post("/import/{batch_id}/confirm-deposit")
def confirm_deposit(batch_id: int, req: DepositConfirmRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.write")
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    pending = batch.pending_deposit_rows
    if req.deposit_index < 0 or req.deposit_index >= len(pending):
        raise HTTPException(status_code=400, detail="Invalid deposit_index.")
    deposit = pending[req.deposit_index]
    if req.confirm_as == "additional":
        if req.client_id is None:
            raise HTTPException(status_code=400, detail="client_id is required when confirm_as='additional'.")
        account = db.query(Account).filter(Account.id == batch.account_id).first()
        if not account:
            raise HTTPException(status_code=400, detail="Batch account not found.")
        from app.services.share_service import subscribe as _subscribe
        from datetime import date as _date
        tx_date = _date.fromisoformat(deposit["date"])
        try:
            _subscribe(db, account.fund_id, req.client_id, tx_date, Decimal(str(deposit["amount_usd"])))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    # Mark this deposit entry as handled
    pending[req.deposit_index]["confirmed_as"] = req.confirm_as
    pending[req.deposit_index]["note"] = req.note
    import json as _json_mod
    batch.pending_deposits = _json_mod.dumps(pending)
    # If all deposits handled, update status
    if all(d.get("confirmed_as") for d in pending):
        batch.status = "confirmed"
    record_audit(
        db, actor, action="import.confirm_deposit",
        entity_type="import_batch", entity_id=str(batch.id),
        detail={"deposit_index": req.deposit_index, "confirm_as": req.confirm_as, "amount_usd": deposit["amount_usd"]},
    )
    db.commit()
    return serialize_batch(batch)


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
    results = rebuild_nav_batch(db, req.fund_id, req.start_date, req.end_date, req.frequency, force=req.force)
    return {"fund_id": req.fund_id, "results": results}


# ---------------------------------------------------------------------------
# PDF Import (annual statement workflow)
# ---------------------------------------------------------------------------

@router.get("/pdf-import")
def list_pdf_batches(
    page: int = Query(DEFAULT_PAGE, ge=1),
    size: int = Query(DEFAULT_SIZE, ge=1, le=MAX_SIZE),
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "import.read")
    query = db.query(PdfImportBatch)
    if account_id:
        query = query.filter(PdfImportBatch.account_id == account_id)
    return _paginate(query.order_by(PdfImportBatch.id.desc()), page, size, serialize_pdf_batch)


@router.post("/pdf-import/upload")
async def upload_pdf(
    account_id: int = Form(...),
    snapshot_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Upload a PDF statement. Returns immediately with status='parsing'. Use polling to check status."""
    require_permissions(actor, "import.write")
    import json as _json
    pdf_bytes = await file.read()
    batch = PdfImportBatch(
        account_id=account_id,
        snapshot_date=snapshot_date,
        filename=file.filename or "upload.pdf",
        status="parsing",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    async def _parse(batch_id: int, content: bytes, acct_id: int):
        import logging as _logging
        _log = _logging.getLogger("pdf_parse_task")
        from app.db import SessionLocal as _SL
        from app.services.pdf_parser_service import parse_pdf_with_ai as _parse_ai
        from app.services.pdf_validator_service import validate_parsed_result as _validate
        db2 = _SL()
        try:
            b = db2.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
            result = await _parse_ai(content)
            if result.get("parse_error"):
                b.status = "failed"
                b.failed_reason = (result.get("raw_text") or "JSON解析失败，模型输出不符合格式要求")[:500]
                _log.error("PDF batch %s parse_error: %s", batch_id, b.failed_reason)
            else:
                # AI-02: run confidence validation against existing DB positions
                try:
                    validation = _validate(result, acct_id, db2)
                    result["_validation"] = validation
                except Exception as ve:
                    _log.warning("Validation step failed (non-fatal): %s", ve)
                b.status = "parsed"
            b.parsed_data = _json.dumps(result, ensure_ascii=False)
            b.ai_model = settings.ollama_model
            db2.commit()
        except Exception as exc:
            _log.exception("PDF batch %s background task failed", batch_id)
            db2.rollback()
            b = db2.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
            if b:
                b.status = "failed"
                b.failed_reason = f"{type(exc).__name__}: {exc}"[:500]
                db2.commit()
        finally:
            db2.close()

    background_tasks.add_task(_parse, batch.id, pdf_bytes, account_id)
    record_audit(db, actor, action="pdf_import.upload", entity_type="pdf_import_batch",
                 entity_id=str(batch.id), detail={"account_id": account_id, "filename": file.filename})
    return serialize_pdf_batch(batch)


@router.get("/pdf-import/{batch_id}")
def get_pdf_batch(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "import.read")
    batch = db.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="PDF import batch not found.")
    return serialize_pdf_batch(batch)


@router.post("/pdf-import/{batch_id}/confirm")
def confirm_pdf_import(batch_id: int, req: PdfImportConfirmRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Confirm a parsed PDF batch: write positions/cash to DB."""
    require_permissions(actor, "import.write")
    import json as _json
    batch = db.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="PDF import batch not found.")
    if req.confirmed_data:
        batch.confirmed_data = _json.dumps(req.confirmed_data)
        db.commit()
    try:
        batch = confirm_pdf_batch(db, batch_id)
        record_audit(db, actor, action="pdf_import.confirm", entity_type="pdf_import_batch",
                     entity_id=str(batch_id), detail={"account_id": batch.account_id, "status": batch.status})
        return serialize_pdf_batch(batch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pdf-import/{batch_id}")
def reset_pdf_import(batch_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Reset/rollback a PDF import batch."""
    require_permissions(actor, "import.write")
    batch = db.query(PdfImportBatch).filter(PdfImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="PDF import batch not found.")
    batch.status = "reset"
    batch.confirmed_data = None
    batch.pending_deposits = None
    db.commit()
    record_audit(db, actor, action="pdf_import.reset", entity_type="pdf_import_batch",
                 entity_id=str(batch_id), detail={"account_id": batch.account_id})
    return serialize_pdf_batch(batch)


# SHR-02: delete share transaction (deposit undo)
@router.delete("/shares/{share_tx_id}")
def delete_share_tx(share_tx_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Undo a share subscription/redemption transaction (admin only)."""
    require_roles(actor, ["admin"])
    tx = db.query(ShareTransaction).filter(ShareTransaction.id == share_tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Share transaction not found.")
    # Roll back fund total shares
    fund = db.query(Fund).filter(Fund.id == tx.fund_id).first()
    if fund:
        if tx.tx_type in ("subscribe", "additional", "seed"):
            fund.total_shares = Decimal(str(fund.total_shares)) - Decimal(str(tx.shares))
        elif tx.tx_type == "redeem":
            fund.total_shares = Decimal(str(fund.total_shares)) + Decimal(str(tx.shares))
    # Roll back ClientCapitalAccount
    from app.models import ClientCapitalAccount as _CCA
    if tx.client_id:
        cca = db.query(_CCA).filter_by(fund_id=tx.fund_id, client_id=tx.client_id).first()
        if cca:
            if tx.tx_type in ("subscribe", "additional", "seed"):
                cca.total_invested_usd = Decimal(str(cca.total_invested_usd)) - Decimal(str(tx.amount_usd))
                cca.current_shares = Decimal(str(cca.current_shares)) - Decimal(str(tx.shares))
            elif tx.tx_type == "redeem":
                cca.total_redeemed_usd = Decimal(str(cca.total_redeemed_usd)) - Decimal(str(tx.amount_usd))
                cca.current_shares = Decimal(str(cca.current_shares)) + Decimal(str(tx.shares))
    # Delete associated share register entries
    db.query(ShareRegister).filter(ShareRegister.ref_share_tx_id == share_tx_id).delete()
    db.delete(tx)
    db.commit()
    record_audit(db, actor, action="shares.delete", entity_type="share_transaction",
                 entity_id=str(share_tx_id), detail={"fund_id": tx.fund_id, "tx_type": tx.tx_type})
    return {"deleted": True}


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
    if req.total_shares is not None:
        fund.total_shares = req.total_shares
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
    for field in ("total_shares", "fund_code", "fund_type", "status", "inception_date", "first_capital_date",
                  "hurdle_rate", "perf_fee_rate", "perf_fee_frequency", "subscription_cycle",
                  "nav_decimal", "share_decimal", "description"):
        val = getattr(req, field, None)
        if val is not None:
            setattr(fund, field, val)
    db.commit()
    db.refresh(fund)
    record_audit(db, actor, action="fund.update", entity_type="fund", entity_id=str(fund.id), detail={"name": fund.name})
    return _serialize_fund(fund)


@router.post("/fund/{fund_id}/seed", status_code=201)
def seed_fund_capital(fund_id: int, req: SeedCapitalRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    from app.models import ShareTransaction as _ShareTx
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found.")
    # Client is optional for seed capital
    client = None
    if req.client_id:
        client = db.query(Client).filter(Client.id == req.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found.")
    seed_nav = Decimal("1.000000")
    shares_issued = Decimal(str(req.shares_override)) if req.shares_override else req.amount_usd / seed_nav
    tx = _ShareTx(
        fund_id=fund_id,
        client_id=req.client_id,
        tx_date=req.seed_date,
        tx_type="seed",
        amount_usd=req.amount_usd,
        shares=shares_issued,
        nav_at_date=seed_nav,
    )
    db.add(tx)
    db.flush()
    # Current shares balance for this client in this fund (before seed)
    shares_after = shares_issued
    if req.client_id:
        existing_balance = db.query(func.sum(_ShareTx.shares)).filter(
            _ShareTx.fund_id == fund_id, _ShareTx.client_id == req.client_id,
            _ShareTx.tx_type.in_(["seed", "subscribe"]),
        ).scalar() or Decimal("0")
        redemptions = db.query(func.sum(_ShareTx.shares)).filter(
            _ShareTx.fund_id == fund_id, _ShareTx.client_id == req.client_id,
            _ShareTx.tx_type == "redeem",
        ).scalar() or Decimal("0")
        shares_after = Decimal(str(existing_balance)) - Decimal(str(redemptions))
    register_entry = ShareRegister(
        fund_id=fund_id,
        client_id=req.client_id,
        event_date=req.seed_date,
        event_type="seed",
        shares_delta=shares_issued,
        shares_after=shares_after,
        nav_per_share=seed_nav,
        amount_usd=req.amount_usd,
        ref_share_tx_id=tx.id,
        note="Seed capital",
    )
    db.add(register_entry)
    fund.total_shares = Decimal(str(fund.total_shares or 0)) + shares_issued
    if not fund.first_capital_date:
        fund.first_capital_date = req.seed_date
    # Upsert capital account (only if client specified)
    if req.client_id:
        capital_acct = db.query(ClientCapitalAccount).filter_by(fund_id=fund_id, client_id=req.client_id).first()
        if not capital_acct:
            capital_acct = ClientCapitalAccount(fund_id=fund_id, client_id=req.client_id)
            db.add(capital_acct)
        capital_acct.total_invested_usd = Decimal(str(capital_acct.total_invested_usd or 0)) + req.amount_usd
        capital_acct.current_shares = Decimal(str(capital_acct.current_shares or 0)) + shares_issued
        capital_acct.avg_cost_nav = seed_nav
        capital_acct.last_updated_date = req.seed_date
    db.commit()
    record_audit(db, actor, action="fund.seed", entity_type="fund", entity_id=str(fund_id),
                 detail={"client_id": req.client_id, "amount_usd": str(req.amount_usd), "shares": str(shares_issued)})
    return {"fund_id": fund_id, "client_id": req.client_id, "shares_issued": _decimal(shares_issued),
            "nav_per_share": _decimal(seed_nav), "amount_usd": _decimal(req.amount_usd), "seed_date": req.seed_date.isoformat()}


@router.post("/fund/{fund_id}/activate")
def activate_fund(fund_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found.")
    fund.status = "active"
    if not fund.inception_date:
        from datetime import date as _date
        fund.inception_date = _date.today()
    db.commit()
    db.refresh(fund)
    record_audit(db, actor, action="fund.activate", entity_type="fund", entity_id=str(fund_id))
    return _serialize_fund(fund)


@router.get("/cash")
def list_cash_positions(
    fund_id: Optional[int] = None,
    account_id: Optional[int] = None,
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "nav.read")
    query = db.query(CashPosition)
    if account_id:
        query = query.filter(CashPosition.account_id == account_id)
    elif fund_id:
        acct_ids = [r[0] for r in db.query(Account.id).filter(Account.fund_id == fund_id).all()]
        if acct_ids:
            query = query.filter(CashPosition.account_id.in_(acct_ids))
        else:
            return []
    if snapshot_date:
        query = query.filter(CashPosition.snapshot_date == snapshot_date)
    rows = query.order_by(CashPosition.snapshot_date.desc(), CashPosition.id.desc()).all()
    return [_serialize_cash(r) for r in rows]


@router.post("/cash", status_code=201)
def upsert_cash_position(req: CashPositionUpsertRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    acct = db.query(Account).filter(Account.id == req.account_id).first()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found.")
    existing = db.query(CashPosition).filter_by(
        account_id=req.account_id, currency=req.currency.upper(), snapshot_date=req.snapshot_date
    ).first()
    if existing:
        before_amount = float(existing.amount)
        existing.amount = req.amount
        if req.note is not None:
            existing.note = req.note
        db.commit()
        db.refresh(existing)
        record_audit(db, actor, action="cash.update", entity_type="cash_position", entity_id=str(existing.id),
                     detail={"account_id": req.account_id, "currency": req.currency.upper(), "snapshot_date": req.snapshot_date.isoformat(),
                             "before_amount": before_amount, "after_amount": float(req.amount), "note": req.note})
        return _serialize_cash(existing)
    row = CashPosition(
        account_id=req.account_id,
        currency=req.currency.upper(),
        amount=req.amount,
        snapshot_date=req.snapshot_date,
        note=req.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(db, actor, action="cash.create", entity_type="cash_position", entity_id=str(row.id),
                 detail={"account_id": req.account_id, "currency": req.currency.upper(), "snapshot_date": req.snapshot_date.isoformat(),
                         "amount": float(req.amount), "note": req.note})
    return _serialize_cash(row)


@router.delete("/cash/{cash_id}", status_code=204)
def delete_cash_position(cash_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "nav.write")
    row = db.query(CashPosition).filter(CashPosition.id == cash_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cash position not found.")
    record_audit(db, actor, action="cash.delete", entity_type="cash_position", entity_id=str(row.id),
                 detail={"account_id": row.account_id, "currency": row.currency, "snapshot_date": row.snapshot_date.isoformat(),
                         "amount": float(row.amount)})
    db.delete(row)
    db.commit()


@router.get("/share/register")
def list_share_register(
    fund_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "shares.read")
    query = db.query(ShareRegister)
    if fund_id:
        query = query.filter(ShareRegister.fund_id == fund_id)
    if client_id:
        query = query.filter(ShareRegister.client_id == client_id)
    rows = query.order_by(ShareRegister.event_date.asc(), ShareRegister.id.asc()).all()
    return [_serialize_register_entry(r) for r in rows]


@router.patch("/share/register/{entry_id}")
def update_share_register_entry(entry_id: int, req: dict, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can edit register entries.")
    entry = db.query(ShareRegister).filter(ShareRegister.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Register entry not found.")
    allowed = {"event_date", "event_type", "shares_delta", "shares_after", "nav_per_share", "amount_usd", "note", "client_id"}
    for key, val in req.items():
        if key in allowed:
            setattr(entry, key, val)
    db.commit()
    db.refresh(entry)
    record_audit(db, actor, action="share_register.update", entity_type="share_register", entity_id=str(entry.id), detail=req)
    return _serialize_register_entry(entry)


@router.delete("/share/register/{entry_id}", status_code=204)
def delete_share_register_entry(entry_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.write")
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete register entries.")
    entry = db.query(ShareRegister).filter(ShareRegister.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Register entry not found.")
    record_audit(db, actor, action="share_register.delete", entity_type="share_register", entity_id=str(entry.id),
                 detail={"fund_id": entry.fund_id, "event_type": entry.event_type, "shares_delta": str(entry.shares_delta)})
    db.delete(entry)
    db.commit()


@router.get("/client/{client_id}/capital-account")
def get_client_capital_accounts(client_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "clients.read")
    rows = db.query(ClientCapitalAccount).filter(ClientCapitalAccount.client_id == client_id).all()
    return [_serialize_capital_account(r) for r in rows]


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
        from app.models import ShareTransaction as _ShareTx
        query = query.join(_ShareTx, _ShareTx.client_id == Client.id).filter(_ShareTx.fund_id == fund_id).distinct()
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
    holder: Optional[str] = None,
    broker: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    require_permissions(actor, "accounts.read")
    query = db.query(Account)
    if fund_id is not None:
        query = query.filter(Account.fund_id == fund_id)
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
        fund_id=req.fund_id,
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
    if req.fund_id is not None:
        item.fund_id = req.fund_id
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
            query = query.filter(Position.account_id == account_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        # Accounts no longer link to clients; client-scoped users see all positions
        pass
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
    fund_id: Optional[int] = None,
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
    if fund_id is not None:
        query = query.join(Account, Account.id == Transaction.account_id).filter(Account.fund_id == fund_id)
    if account_id is not None:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            query = query.filter(Transaction.account_id == account_id)
    elif actor.role == ROLE_CLIENT_READONLY:
        pass
    if trade_date is not None:
        query = query.filter(Transaction.trade_date == trade_date)
    if date_from is not None:
        query = query.filter(Transaction.trade_date >= date_from)
    if date_to is not None:
        query = query.filter(Transaction.trade_date <= date_to)
    if tx_category is not None:
        # Support legacy aliases: EQUITY→TRADE
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
            detail=f"CSV导入记录请通过「重置批次」操作删除，不能单条删除。(batch #{tx.import_batch_id})",
        )

    # Protection 2: Check for locked NAV records after this transaction's date
    locked_nav = db.query(NAVRecord).filter(
        NAVRecord.fund_id == db.query(Account.fund_id).filter(Account.id == tx.account_id).scalar_subquery(),
        NAVRecord.nav_date >= tx.trade_date,
        NAVRecord.is_locked == True,
    ).first()
    if locked_nav:
        raise HTTPException(
            status_code=400,
            detail=f"该交易日期之后存在已锁定NAV记录（{locked_nav.nav_date}），无法删除。请先解锁NAV记录。",
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


@router.get("/customer/{client_id}")
def get_customer_view(client_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    require_permissions(actor, "customer.read")
    require_client_scope(actor, client_id)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    account_rows = []  # Accounts no longer link to clients
    fund_ids = _client_fund_ids(db, client_id)
    share_balance_rows = balances(db, client_id=client_id)
    share_history_rows = history(db, client_id=client_id)
    nav_rows = [_serialize_nav(item, db) for item in list_nav(db)]
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
    nav_rows = [_serialize_nav(item, db) for item in nav_query.order_by(NAVRecord.nav_date.desc(), NAVRecord.id.desc()).all()]

    fee_rows = []
    if actor.role != ROLE_CLIENT_READONLY:
        fee_query = db.query(FeeRecord).filter(and_(FeeRecord.fee_date >= start_date, FeeRecord.fee_date <= end_date))
        if fund_id is not None:
            fee_query = fee_query.filter(FeeRecord.fund_id == fund_id)
        fee_rows = [_serialize_fee(item) for item in fee_query.order_by(FeeRecord.fee_date.desc(), FeeRecord.id.desc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    if fund_id is not None:
        transaction_query = transaction_query.join(Account, Account.id == Transaction.account_id).filter(Account.fund_id == fund_id)
    # client_id / client-scope filtering no longer possible via Account (no client_id FK)
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
    nav_rows = [_serialize_nav(item, db) for item in nav_query.order_by(NAVRecord.nav_date.asc()).all()]

    fee_rows = []
    if actor.role != ROLE_CLIENT_READONLY:
        fee_query = db.query(FeeRecord).filter(and_(FeeRecord.fee_date >= start_date, FeeRecord.fee_date <= end_date))
        if fund_id is not None:
            fee_query = fee_query.filter(FeeRecord.fund_id == fund_id)
        fee_rows = [_serialize_fee(item) for item in fee_query.order_by(FeeRecord.fee_date.asc()).all()]

    transaction_query = db.query(Transaction).filter(and_(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date))
    if fund_id is not None:
        transaction_query = transaction_query.join(Account, Account.id == Transaction.account_id).filter(Account.fund_id == fund_id)
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
    """Get fund IDs where this client has share transactions."""
    if client_id is None:
        return []
    from app.models import ShareTransaction as _ShareTx
    return sorted({row[0] for row in db.query(_ShareTx.fund_id).filter(_ShareTx.client_id == client_id).distinct().all()})


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
        "fund_code": item.fund_code,
        "inception_date": _iso(item.inception_date),
        "first_capital_date": _iso(item.first_capital_date),
        "fund_type": item.fund_type,
        "status": item.status,
        "hurdle_rate": _decimal(item.hurdle_rate),
        "perf_fee_rate": _decimal(item.perf_fee_rate),
        "perf_fee_frequency": item.perf_fee_frequency,
        "subscription_cycle": item.subscription_cycle,
        "nav_decimal": item.nav_decimal,
        "share_decimal": item.share_decimal,
        "description": item.description,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _serialize_client(db: Session, item: Client) -> dict:
    from decimal import Decimal as _D
    from app.models import ShareTransaction as _ShareTx
    share_balance_rows = balances(db, client_id=item.id)
    total_share_balance = sum(row["share_balance"] for row in share_balance_rows)
    fund_ids = sorted({row["fund_id"] for row in share_balance_rows})
    share_history_rows = history(db, client_id=item.id)
    latest_share_event_date = share_history_rows[0]["tx_date"] if share_history_rows else None

    # Compute holding value: shares × latest locked NAV per share, per fund
    total_holding_usd = _D("0")
    for row in share_balance_rows:
        f_id = row["fund_id"]
        latest_nav = db.query(NAVRecord).filter(
            NAVRecord.fund_id == f_id,
            NAVRecord.is_locked == True,  # noqa: E712
        ).order_by(NAVRecord.nav_date.desc()).first()
        if latest_nav and latest_nav.nav_per_share:
            total_holding_usd += _D(str(row["share_balance"])) * _D(str(latest_nav.nav_per_share))

    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "fund_count": len(fund_ids),
        "fund_ids": fund_ids,
        "total_share_balance": total_share_balance,
        "total_holding_value_usd": float(total_holding_usd),
        "holding_currency": "USD",
        "share_tx_count": len(share_history_rows),
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

    # Snapshot cost-basis value (quantity × average_cost) for latest snapshot date
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
        "fund_id": item.fund_id,
        "fund_name": fund.name if fund else None,
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


def _serialize_nav(item, db: Session = None) -> dict:
    fund_name = None
    if db is not None:
        _fund = db.query(Fund).filter(Fund.id == item.fund_id).first()
        fund_name = _fund.name if _fund else None
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "fund_name": fund_name,
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


def _serialize_register_entry(item: ShareRegister) -> dict:
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "client_id": item.client_id,
        "event_date": _iso(item.event_date),
        "event_type": item.event_type,
        "shares_delta": _decimal(item.shares_delta),
        "shares_after": _decimal(item.shares_after),
        "nav_per_share": _decimal(item.nav_per_share),
        "amount_usd": _decimal(item.amount_usd),
        "ref_share_tx_id": item.ref_share_tx_id,
        "note": item.note,
        "created_at": _iso(item.created_at),
    }


def _serialize_capital_account(item: ClientCapitalAccount) -> dict:
    return {
        "id": item.id,
        "fund_id": item.fund_id,
        "client_id": item.client_id,
        "total_invested_usd": _decimal(item.total_invested_usd),
        "total_redeemed_usd": _decimal(item.total_redeemed_usd),
        "avg_cost_nav": _decimal(item.avg_cost_nav),
        "current_shares": _decimal(item.current_shares),
        "unrealized_pnl_usd": _decimal(item.unrealized_pnl_usd),
        "last_updated_date": _iso(item.last_updated_date),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
