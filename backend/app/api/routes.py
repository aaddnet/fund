from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import FeeCalcRequest, NavCalcRequest, PriceFetchRequest, RateFetchRequest, ShareRequest
from app.services.exchange_rate import fetch_and_save_rates, list_rates
from app.services.fee_service import calc_fee, list_fees
from app.services.import_service import confirm_batch, get_batch, list_batches, serialize_batch, upload_csv
from app.services.nav_engine import calc_nav, list_nav
from app.services.price_service import fetch_and_save_prices
from app.services.share_service import history, redeem, subscribe

router = APIRouter()


@router.post("/rates/fetch")
def fetch_rates(req: RateFetchRequest, db: Session = Depends(get_db)):
    return fetch_and_save_rates(db, req.base, req.quote, req.snapshot_date)


@router.get("/rates")
def get_rates(db: Session = Depends(get_db)):
    return list_rates(db)


@router.post("/price/fetch")
def fetch_price(req: PriceFetchRequest, db: Session = Depends(get_db)):
    return fetch_and_save_prices(db, req.assets, req.snapshot_date)


@router.post("/nav/calc")
def run_nav(req: NavCalcRequest, db: Session = Depends(get_db)):
    return calc_nav(db, req.fund_id, req.nav_date)


@router.get("/nav")
def get_nav_records(db: Session = Depends(get_db)):
    return list_nav(db)


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


# placeholder CRUD endpoints for V1 API scope
for resource in ["fund", "client", "account", "position", "transaction", "rate", "price"]:
    @router.get(f"/{resource}")
    def _list(resource_name=resource):
        return {"resource": resource_name, "items": [], "pagination": {"page": 1, "size": 20, "total": 0}}
