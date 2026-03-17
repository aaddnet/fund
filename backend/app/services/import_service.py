from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Account, ImportBatch, Position, Transaction

IMPORT_STATUS_UPLOADED = "uploaded"
IMPORT_STATUS_PARSED = "parsed"
IMPORT_STATUS_CONFIRMED = "confirmed"
IMPORT_STATUS_FAILED = "failed"
REQUIRED_COLUMNS = {"trade_date", "asset_code", "quantity", "price", "currency", "tx_type"}


def list_batches(db: Session) -> list[ImportBatch]:
    return db.query(ImportBatch).order_by(ImportBatch.id.desc()).all()


def get_batch(db: Session, batch_id: int) -> Optional[ImportBatch]:
    return db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()


def upload_csv(db: Session, source: str, filename: str, account_id: int, content: bytes) -> ImportBatch:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} does not exist.")

    batch = ImportBatch(
        source=source.lower().strip() or "csv",
        filename=filename,
        account_id=account_id,
        status=IMPORT_STATUS_UPLOADED,
        imported_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()

    try:
        rows = _parse_csv_rows(content)
        batch.row_count = len(rows)
        batch.parsed_count = len(rows)
        batch.preview_json = json.dumps(rows)
        batch.status = IMPORT_STATUS_PARSED
        batch.failed_reason = None
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

    for item in preview_rows:
        db.add(
            Transaction(
                account_id=batch.account_id,
                trade_date=_parse_date_value(item["trade_date"]),
                asset_code=item["asset_code"],
                quantity=Decimal(str(item["quantity"])),
                price=Decimal(str(item["price"])),
                currency=item["currency"],
                tx_type=item["tx_type"],
                fee=Decimal(str(item.get("fee", "0"))),
                import_batch_id=batch.id,
            )
        )

    positions = _build_positions(batch.account_id, preview_rows)
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
            )
        )

    batch.confirmed_count = len(preview_rows)
    batch.status = IMPORT_STATUS_CONFIRMED
    batch.failed_reason = None
    db.commit()
    db.refresh(batch)
    return batch


def serialize_batch(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "source": batch.source,
        "filename": batch.filename,
        "account_id": batch.account_id,
        "status": batch.status,
        "row_count": batch.row_count,
        "parsed_count": batch.parsed_count,
        "confirmed_count": batch.confirmed_count,
        "failed_reason": batch.failed_reason,
        "imported_at": batch.imported_at.isoformat() if batch.imported_at else None,
        "preview_rows": batch.preview_rows,
    }


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

        if quantity == 0:
            raise ValueError(f"Row {index}: quantity cannot be zero.")

        tx_type = (normalized["tx_type"] or "trade").lower()
        snapshot_date = normalized.get("snapshot_date") or trade_date.isoformat()
        parsed_rows.append(
            {
                "row_number": index,
                "trade_date": trade_date.isoformat(),
                "asset_code": normalized["asset_code"].upper(),
                "quantity": str(quantity),
                "price": str(price),
                "currency": (normalized["currency"] or "USD").upper(),
                "tx_type": tx_type,
                "fee": str(fee),
                "snapshot_date": _parse_date_value(snapshot_date).isoformat(),
            }
        )

    if not parsed_rows:
        raise ValueError("CSV did not contain any usable rows.")

    return parsed_rows


def _build_positions(account_id: int, preview_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Decimal | str | date]] = defaultdict(
        lambda: {
            "quantity": Decimal("0"),
            "cost_basis": Decimal("0"),
        }
    )

    for item in sorted(preview_rows, key=lambda row: (row["snapshot_date"], row["asset_code"], row["trade_date"], row["row_number"])):
        key = (item["snapshot_date"], item["asset_code"], item["currency"])
        bucket = grouped[key]
        quantity = Decimal(str(item["quantity"]))
        price = Decimal(str(item["price"]))
        fee = Decimal(str(item.get("fee", "0")))
        bucket["quantity"] += quantity
        bucket["cost_basis"] += (quantity * price) + fee

    positions: list[dict[str, Any]] = []
    for (snapshot_date, asset_code, currency), bucket in grouped.items():
        quantity = Decimal(str(bucket["quantity"]))
        if quantity == 0:
            continue
        cost_basis = Decimal(str(bucket["cost_basis"]))
        average_cost = (cost_basis / quantity.copy_abs()) if quantity != 0 else Decimal("0")
        positions.append(
            {
                "account_id": account_id,
                "asset_code": asset_code,
                "quantity": quantity,
                "average_cost": average_cost,
                "currency": currency,
                "snapshot_date": _parse_date_value(snapshot_date),
            }
        )

    return positions


def _normalize_column_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _parse_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _parse_date_value(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc

