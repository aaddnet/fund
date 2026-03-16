from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import FeeCalcRequest, NavCalcRequest, PriceFetchRequest, RateFetchRequest, ShareRequest
from app.services.exchange_rate import fetch_and_save_rates, list_rates
from app.services.fee_service import calc_fee, list_fees
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
def get_nav(db: Session = Depends(get_db)):
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


# placeholder CRUD endpoints for V1 API scope
for resource in ["fund", "client", "account", "position", "transaction", "rate", "price", "import"]:
    @router.get(f"/{resource}")
    def _list(resource_name=resource):
        return {"resource": resource_name, "items": [], "pagination": {"page": 1, "size": 20, "total": 0}}
