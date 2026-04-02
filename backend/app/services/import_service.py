from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Account, CashPosition, ImportBatch, Position, Transaction
from app.services.parser import ib_parser, kraken_parser, moomoo_parser, schwab_parser

IMPORT_STATUS_UPLOADED = "uploaded"
IMPORT_STATUS_PARSED = "parsed"
IMPORT_STATUS_CONFIRMED = "confirmed"
IMPORT_STATUS_FAILED = "failed"
REQUIRED_COLUMNS = {"trade_date", "asset_code", "quantity", "price", "currency", "tx_type"}
COLUMN_ALIASES = {
    "date": "trade_date",
    "tradedate": "trade_date",
    "trade_date": "trade_date",
    "transaction_date": "trade_date",
    "symbol": "asset_code",
    "ticker": "asset_code",
    "security": "asset_code",
    "asset": "asset_code",
    "asset_code": "asset_code",
    "qty": "quantity",
    "shares": "quantity",
    "amount": "quantity",
    "quantity": "quantity",
    "execution_price": "price",
    "unit_price": "price",
    "trade_price": "price",
    "price": "price",
    "ccy": "currency",
    "fx_currency": "currency",
    "currency": "currency",
    "side": "tx_type",
    "action": "tx_type",
    "type": "tx_type",
    "tx_type": "tx_type",
    "commission": "fee",
    "fees": "fee",
    "fee": "fee",
    "as_of": "snapshot_date",
    "position_date": "snapshot_date",
    "snapshot_date": "snapshot_date",
    # V4.1: optional extended columns
    "description": "description",
    "tx_subtype": "tx_subtype",
    "gross_amount": "gross_amount",
    "commission_amount": "commission",
    "transaction_fee": "transaction_fee",
    "other_fee": "other_fee",
    "isin": "isin",
    "exchange": "exchange",
    "counterparty_account": "counterparty_account",
}
BUY_TX_TYPES = {"buy", "b", "subscribe", "sub"}
SELL_TX_TYPES = {"sell", "s", "redeem", "redemption", "withdrawal"}
# Forex/cash tx types are pass-through — not normalized to buy/sell
FOREX_CASH_TX_TYPES = {"forex_buy", "forex_sell", "cash_in", "cash_out"}
# Deposit rows flagged for manual capital-event confirmation (never auto-create Position)
DEPOSIT_PENDING_TX_TYPE = "deposit_pending"

# V4.1: Extended category sets
_ACCRUAL_TX_TYPES = {
    "interest_accrual", "interest_accrual_reversal",
    "dividend_accrual", "dividend_accrual_reversal",
}
_SECURITIES_LENDING_TX_TYPES = {"lending_out", "lending_return"}
_CASH_TX_TYPES = {
    "cash_in", "cash_out", "deposit", "withdrawal",
    "dividend", "dividend_tax", "interest_credit", "interest_debit",
    "fee", "adjustment", "margin_interest", "margin_adjustment",
    # V4.1 additions
    "transfer", "pil", "dividend_fee", "adr_fee", "other_fee",
    "lending_income",
}

# Map import source name → platform-specific preprocessor
_PREPROCESSORS = {
    "ib": ib_parser.preprocess,
    "interactive_brokers": ib_parser.preprocess,
    "kraken": kraken_parser.preprocess,
    "schwab": schwab_parser.preprocess,
    "charles_schwab": schwab_parser.preprocess,
    "moomoo": moomoo_parser.preprocess,
    "futu": moomoo_parser.preprocess,
}


def list_batches(db: Session) -> list[ImportBatch]:
    return db.query(ImportBatch).order_by(ImportBatch.id.desc()).all()


def get_batch(db: Session, batch_id: int) -> Optional[ImportBatch]:
    return db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()


def upload_csv(db: Session, source: str, filename: str, account_id: int, content: bytes, force: bool = False) -> ImportBatch:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} does not exist.")

    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.query(ImportBatch).filter(ImportBatch.file_hash == file_hash).first()
    if existing and not force:
        raise ValueError(f"duplicate_file:{existing.id}")

    batch = ImportBatch(
        source=source.lower().strip() or "csv",
        filename=filename,
        account_id=account_id,
        status=IMPORT_STATUS_UPLOADED,
        file_hash=file_hash,
        imported_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()

    try:
        preprocessor = _PREPROCESSORS.get(source.lower().strip())
        payload = preprocessor(content) if preprocessor else content
        rows = _parse_csv_rows(payload)
        batch.row_count = len(rows)
        batch.parsed_count = len(rows)
        batch.preview_json = json.dumps(rows)
        batch.status = IMPORT_STATUS_PARSED
        batch.failed_reason = None

        # Overlap detection: count existing transactions for same account in the same date range
        overlap_info = _check_overlap(db, account_id, rows)
        if overlap_info["overlap_count"] > 0:
            batch.failed_reason = json.dumps({"overlap": overlap_info})

        db.commit()
        db.refresh(batch)
        return batch
    except Exception as exc:
        # 注意这里要把失败状态持久化，方便前端排查导入问题。
        batch.status = IMPORT_STATUS_FAILED
        batch.failed_reason = str(exc)
        batch.preview_json = json.dumps([])
        batch.row_count = 0
        batch.parsed_count = 0
        db.commit()
        db.refresh(batch)
        return batch


def _check_overlap(db: Session, account_id: int, rows: list[dict]) -> dict:
    """Check how many existing transactions fall in the same date range as the new rows."""
    trade_dates = []
    for r in rows:
        try:
            trade_dates.append(_parse_date_value(r["trade_date"]))
        except Exception:
            pass
    if not trade_dates:
        return {"overlap_count": 0, "min_date": None, "max_date": None}

    min_date = min(trade_dates)
    max_date = max(trade_dates)

    overlap_count = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.trade_date >= min_date,
            Transaction.trade_date <= max_date,
        )
        .count()
    )
    return {
        "overlap_count": overlap_count,
        "min_date": min_date.isoformat(),
        "max_date": max_date.isoformat(),
    }


def confirm_batch(db: Session, batch_id: int) -> ImportBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError(f"Import batch {batch_id} was not found.")
    if batch.status == IMPORT_STATUS_CONFIRMED:
        return batch
    if batch.status != IMPORT_STATUS_PARSED:
        raise ValueError("Only parsed batches can be confirmed.")

    preview_rows = batch.preview_rows
    if not preview_rows:
        raise ValueError("This batch has no parsed rows to confirm.")

    # Separate deposit rows (pending capital events) from trade/cash rows
    trade_rows = [r for r in preview_rows if r["tx_type"] != DEPOSIT_PENDING_TX_TYPE]
    deposit_rows = [r for r in preview_rows if r["tx_type"] == DEPOSIT_PENDING_TX_TYPE]

    for item in trade_rows:
        tx_type_lower = (item["tx_type"] or "").lower()
        # V4.2: Extended category routing (TRADE replaces EQUITY)
        if tx_type_lower in ("forex_buy", "forex_sell", "fx_translation", "fx_trade", "fx"):
            tx_category = "FX"
        elif tx_type_lower in _ACCRUAL_TX_TYPES:
            tx_category = "ACCRUAL"
        elif tx_type_lower in (_SECURITIES_LENDING_TX_TYPES | {"lending_income"}):
            tx_category = "LENDING"
        elif tx_type_lower in _CASH_TX_TYPES or tx_type_lower in (
            "deposit_eft", "deposit_transfer", "withdrawal", "dividend", "pil",
            "dividend_fee", "interest_debit", "interest_credit", "adr_fee",
            "other_fee", "adjustment", "lending_income",
        ):
            tx_category = "CASH"
        elif tx_type_lower in ("stock_buy", "stock_sell", "option_buy", "option_sell",
                               "option_expire", "option_exercise",
                               "stock_split", "reverse_split", "rights_issue", "spinoff", "merger"):
            tx_category = "TRADE"
        else:
            tx_category = "TRADE"  # default (was EQUITY)

        def _opt_decimal(val: Any) -> Optional[Decimal]:
            if val is None or val == "":
                return None
            try:
                return Decimal(str(val))
            except Exception:
                return None

        db.add(
            Transaction(
                account_id=batch.account_id,
                trade_date=_parse_date_value(item["trade_date"]),
                asset_code=item.get("asset_code") or None,
                quantity=_opt_decimal(item.get("quantity")),
                price=_opt_decimal(item.get("price")),
                currency=item["currency"],
                tx_type=item["tx_type"],
                fee=Decimal(str(item.get("fee", "0"))),
                import_batch_id=batch.id,
                tx_category=tx_category,
                source="csv_import",
                # V4.1: extended fields from parser output
                tx_subtype=item.get("tx_subtype") or None,
                description=item.get("description") or None,
                amount=_opt_decimal(item.get("gross_amount")),
                commission=_opt_decimal(item.get("commission")),
                transaction_fee=_opt_decimal(item.get("transaction_fee")),
                other_fee=_opt_decimal(item.get("other_fee")),
                isin=item.get("isin") or None,
                exchange=item.get("exchange") or None,
                counterparty_account=item.get("counterparty_account") or None,
            )
        )

    positions = _build_positions(batch.account_id, trade_rows)
    snapshot_dates = {position["snapshot_date"] for position in positions}
    for snapshot_date in snapshot_dates:
        db.query(Position).filter(
            Position.account_id == batch.account_id,
            Position.snapshot_date == snapshot_date,
        ).delete(synchronize_session=False)

    for position in positions:
        db.add(
            Position(
                account_id=batch.account_id,
                asset_code=position["asset_code"],
                quantity=position["quantity"],
                average_cost=position["average_cost"],
                currency=position["currency"],
                snapshot_date=position["snapshot_date"],
                source_batch_id=batch.id,
            )
        )

    # Generate CashPosition snapshots from forex/cash transactions
    _build_cash_positions(db, batch.account_id, trade_rows, source_batch_id=batch.id)

    # Store deposit rows in pending_deposits for manual confirmation
    if deposit_rows:
        pending = [
            {
                "date": r["trade_date"],
                "amount_usd": float(r["quantity"]),
                "tx_type": r["tx_type"],
                "currency": r["currency"],
                "note": r.get("asset_code", ""),
            }
            for r in deposit_rows
        ]
        batch.pending_deposits = json.dumps(pending)
        batch.status = "confirmed_pending_deposits"
    else:
        batch.status = IMPORT_STATUS_CONFIRMED

    batch.confirmed_count = len(trade_rows)
    batch.failed_reason = None
    db.commit()

    # V4.2: Trigger position recalculation for all TRADE assets in this batch
    try:
        from app.services.position_calculator import recalculate_all_positions
        recalculate_all_positions(batch.account_id, db)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"position recalc after import failed: {exc}")

    db.refresh(batch)
    return batch


def serialize_batch(batch: ImportBatch) -> dict[str, Any]:
    # Separate overlap warning from regular failure reasons
    overlap_info = None
    display_reason = batch.failed_reason
    if batch.failed_reason:
        try:
            parsed = json.loads(batch.failed_reason)
            if isinstance(parsed, dict) and "overlap" in parsed:
                overlap_info = parsed["overlap"]
                display_reason = None   # not a failure, just a warning
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": batch.id,
        "source": batch.source,
        "filename": batch.filename,
        "account_id": batch.account_id,
        "status": batch.status,
        "row_count": batch.row_count,
        "parsed_count": batch.parsed_count,
        "confirmed_count": batch.confirmed_count,
        "failed_reason": display_reason,
        "overlap": overlap_info,   # { overlap_count, min_date, max_date } or null
        "imported_at": batch.imported_at.isoformat() if batch.imported_at else None,
        "preview_rows": batch.preview_rows,
        "pending_deposits": batch.pending_deposit_rows,
    }


def reset_batch(db: Session, batch_id: int) -> ImportBatch:
    """Roll back all data created by this import batch (transactions, positions, cash positions)."""
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError(f"Import batch {batch_id} was not found.")

    db.query(Transaction).filter(Transaction.import_batch_id == batch_id).delete()
    db.query(Position).filter(Position.source_batch_id == batch_id).delete()
    db.query(CashPosition).filter(CashPosition.source_batch_id == batch_id).delete()
    batch.pending_deposits = None
    batch.status = "reset"
    batch.confirmed_count = 0
    batch.failed_reason = None
    db.commit()
    db.refresh(batch)
    return batch


def _parse_csv_rows(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV header is required.")

    normalized_fieldnames = {_normalize_column_name(name) for name in reader.fieldnames if name}
    missing_columns = REQUIRED_COLUMNS - normalized_fieldnames
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"CSV is missing required columns: {missing}.")

    parsed_rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in raw_row.values()):
            continue
        normalized = {_normalize_column_name(key): (value or "").strip() for key, value in raw_row.items() if key}
        try:
            trade_date = _parse_date_value(normalized["trade_date"])
            quantity = _parse_decimal(normalized["quantity"], "quantity")
            price = _parse_decimal(normalized["price"], "price")
            fee = _parse_decimal(normalized.get("fee") or "0", "fee")
        except ValueError as exc:
            raise ValueError(f"Row {index}: {exc}") from exc

        tx_type = _normalize_tx_type(normalized["tx_type"])
        quantity = _normalize_quantity_for_tx_type(quantity, tx_type)
        if quantity == 0:
            raise ValueError(f"Row {index}: quantity cannot be zero.")

        snapshot_date = normalized.get("snapshot_date") or trade_date.isoformat()
        parsed_rows.append(
            {
                "row_number": index,
                "trade_date": trade_date.isoformat(),
                "asset_code": normalized.get("asset_code", "").upper(),
                "quantity": str(quantity),
                "price": str(price),
                "currency": (normalized.get("currency") or "USD").upper(),
                "tx_type": tx_type,
                "fee": str(fee),
                "snapshot_date": _parse_date_value(snapshot_date).isoformat(),
                # V4.1: optional extended fields (passed through if present)
                "tx_subtype": normalized.get("tx_subtype") or "",
                "description": normalized.get("description") or "",
                "gross_amount": normalized.get("gross_amount") or "",
                "commission": normalized.get("commission") or "",
                "transaction_fee": normalized.get("transaction_fee") or "",
                "other_fee": normalized.get("other_fee") or "",
                "isin": normalized.get("isin") or "",
                "exchange": normalized.get("exchange") or "",
                "counterparty_account": normalized.get("counterparty_account") or "",
            }
        )

    if not parsed_rows:
        raise ValueError("CSV did not contain any usable rows.")

    return parsed_rows


def _build_positions(account_id: int, preview_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict
    from decimal import Decimal

    position_state = defaultdict(lambda: {"quantity": Decimal("0"), "cost_basis": Decimal("0")})
    snapshots = {}

    for item in sorted(preview_rows, key=lambda row: (row["snapshot_date"], row["trade_date"], row["row_number"], row.get("asset_code", ""))):
        # Skip forex/cash/deposit/accrual/lending rows — they don't create stock positions
        tx_t = item["tx_type"]
        _NON_TRADE = (
            FOREX_CASH_TX_TYPES | _CASH_TX_TYPES | _ACCRUAL_TX_TYPES | _SECURITIES_LENDING_TX_TYPES
            | {DEPOSIT_PENDING_TX_TYPE, "fx_translation", "fx_trade", "fx",
               "deposit_eft", "deposit_transfer", "withdrawal", "dividend", "pil",
               "dividend_fee", "interest_debit", "interest_credit", "adr_fee",
               "other_fee", "adjustment", "lending_income",
               "interest_accrual", "dividend_accrual", "interest_accrual_reversal",
               "dividend_accrual_reversal"}
        )
        if (tx_t in _NON_TRADE):
            continue
        position_key = (item["asset_code"], item["currency"])
        state = position_state[position_key]
        quantity = Decimal(str(item["quantity"]))
        price = Decimal(str(item["price"]))
        fee = Decimal(str(item.get("fee", "0")))

        if quantity > 0:
            state["quantity"] += quantity
            state["cost_basis"] += (quantity * price) + fee
        else:
            sell_quantity = abs(quantity)
            current_quantity = state["quantity"]
            if current_quantity > 0 and sell_quantity <= current_quantity:
                average_cost = state["cost_basis"] / current_quantity
                state["quantity"] = current_quantity - sell_quantity
                state["cost_basis"] = state["cost_basis"] - (average_cost * sell_quantity)
                if fee:
                    state["cost_basis"] += fee
                if state["quantity"] == 0:
                    state["cost_basis"] = Decimal("0")
            else:
                # Partial-period import: position existed before this file.
                # Allow negative quantity (will be excluded from final positions).
                state["quantity"] = current_quantity - sell_quantity
                state["cost_basis"] = Decimal("0")

        snapshots[(item["snapshot_date"], item["asset_code"], item["currency"])] = {
            "account_id": account_id,
            "asset_code": item["asset_code"],
            "quantity": str(state["quantity"]),
            "average_cost": str((state["cost_basis"] / state["quantity"]) if state["quantity"] != 0 else Decimal("0")),
            "currency": item["currency"],
            "snapshot_date": item["snapshot_date"],
        }

    positions = []
    for position in snapshots.values():
        quantity = Decimal(str(position["quantity"]))
        if quantity == 0:
            continue
        positions.append(position)

    return sorted(positions, key=lambda row: (row["snapshot_date"], row["asset_code"], row["currency"]))


def _build_cash_positions(db: Session, account_id: int, preview_rows: list[dict[str, Any]], source_batch_id: Optional[int] = None) -> None:
    """
    Build CashPosition snapshots from forex/cash rows.

    For forex trades (e.g. forex_buy EUR.USD qty=10000 price=1.12):
      - Base currency (EUR): +10000
      - Quote currency (USD): -10000 * 1.12 = -11200
    For cash_in/cash_out: direct currency amount.

    Amounts are accumulated per (currency, snapshot_date) and upserted.
    """
    cash_deltas: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))  # (currency, snapshot_date) → delta

    for item in preview_rows:
        tx_type = item["tx_type"]
        if tx_type not in FOREX_CASH_TX_TYPES:
            continue

        qty = Decimal(str(item["quantity"]))
        price = Decimal(str(item["price"]))
        snapshot_date = item["snapshot_date"]
        asset_code = item["asset_code"]  # e.g. "EUR.USD" for forex
        trade_currency = item["currency"]

        if tx_type in ("forex_buy", "forex_sell"):
            # Parse currency pair from asset_code (e.g. "EUR.USD", "EUR/USD", "EURUSD")
            base_ccy, quote_ccy = _parse_currency_pair(asset_code, trade_currency)
            notional = qty * price
            if tx_type == "forex_buy":
                cash_deltas[(base_ccy, snapshot_date)] += qty
                cash_deltas[(quote_ccy, snapshot_date)] -= notional
            else:  # forex_sell
                cash_deltas[(base_ccy, snapshot_date)] -= qty
                cash_deltas[(quote_ccy, snapshot_date)] += notional
        elif tx_type == "cash_in":
            cash_deltas[(trade_currency, snapshot_date)] += qty
        elif tx_type == "cash_out":
            cash_deltas[(trade_currency, snapshot_date)] -= qty

    # Upsert CashPosition for each (currency, date) with non-zero delta
    for (currency, snapshot_date_str), delta in cash_deltas.items():
        if delta == 0:
            continue
        snap_date = _parse_date_value(snapshot_date_str)
        existing = db.query(CashPosition).filter_by(
            account_id=account_id, currency=currency, snapshot_date=snap_date,
        ).first()
        if existing:
            existing.amount = Decimal(str(existing.amount)) + delta
            existing.note = (existing.note or "") + "; import_adjusted"
        else:
            db.add(CashPosition(
                account_id=account_id,
                currency=currency,
                amount=delta,
                snapshot_date=snap_date,
                note="auto_from_import",
                source_batch_id=source_batch_id,
            ))


def _parse_currency_pair(asset_code: str, fallback_quote: str) -> tuple[str, str]:
    """
    Parse forex pair into (base, quote) currencies.
    Handles: EUR.USD, EUR/USD, EURUSD (6 char)
    """
    asset = asset_code.upper().strip()
    for sep in (".", "/", "-"):
        if sep in asset:
            parts = asset.split(sep, 1)
            if len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3:
                return parts[0], parts[1]
    # No separator — try 6-char pair (EURUSD)
    if len(asset) == 6 and asset.isalpha():
        return asset[:3], asset[3:]
    # Fallback: treat asset_code as base currency, use trade currency as quote
    return asset, fallback_quote.upper()


def _normalize_column_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    normalized = normalized.replace("-", "_")
    return COLUMN_ALIASES.get(normalized, normalized)


def _normalize_tx_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if normalized in FOREX_CASH_TX_TYPES:
        return normalized
    if normalized == DEPOSIT_PENDING_TX_TYPE:
        return DEPOSIT_PENDING_TX_TYPE
    if normalized in BUY_TX_TYPES:
        return "buy"
    if normalized in SELL_TX_TYPES:
        return "sell"
    return normalized or "trade"


def _normalize_quantity_for_tx_type(quantity: Decimal, tx_type: str) -> Decimal:
    if tx_type in FOREX_CASH_TX_TYPES or tx_type == DEPOSIT_PENDING_TX_TYPE:
        return quantity.copy_abs()  # always positive, direction is in tx_type
    if tx_type == "sell" and quantity > 0:
        return quantity * Decimal("-1")
    if tx_type == "buy" and quantity < 0:
        return quantity.copy_abs()
    return quantity


def _parse_decimal(value: str, field_name: str) -> Decimal:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"invalid {field_name}: {value}")
    negative = normalized.startswith("(") and normalized.endswith(")")
    normalized = normalized.strip("()")
    normalized = normalized.replace(",", "").replace("$", "")
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc
    return parsed * Decimal("-1") if negative else parsed


def _parse_date_value(value: str) -> date:
    normalized = str(value or "").strip()
    for formatter in (date.fromisoformat,):
        try:
            return formatter(normalized)
        except ValueError:
            pass

    for pattern in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date: {value}")
