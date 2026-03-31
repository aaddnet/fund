"""AI-02: Confidence validation service for PDF import batches.

Compares AI-parsed positions against existing DB records.
Flags differences exceeding thresholds to guide human review.

Thresholds:
  error   (red, blocks auto-confirm): qty diff > 20%
  warning (orange, advisory):         qty diff > 5%
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Position

logger = logging.getLogger(__name__)

_WARN_THRESHOLD  = 0.05   # 5%
_ERROR_THRESHOLD = 0.20   # 20%


def validate_parsed_result(parsed: dict, account_id: int, db: Session) -> dict:
    """
    Compare parsed positions against most-recent DB snapshot for the same account.

    Returns:
        {
            "errors":           [...],   # diff > 20% — red, confirm blocked
            "warnings":         [...],   # diff > 5%  — orange, advisory
            "new_positions":    [...],   # not in DB at all
            "can_auto_confirm": bool,    # True only when no errors
            "summary": {"total": int, "matched": int, "warnings": int, "errors": int, "new": int}
        }
    """
    warnings: list[dict] = []
    errors:   list[dict] = []
    new_positions: list[dict] = []

    positions = parsed.get("positions", [])

    for pos in positions:
        asset_code = str(pos.get("asset_code") or "").strip().upper()
        if not asset_code:
            continue

        ai_qty = pos.get("quantity")
        if ai_qty is None:
            continue

        try:
            ai_qty = float(ai_qty)
        except (TypeError, ValueError):
            continue

        # Look up most-recent snapshot for this account + asset
        existing = (
            db.query(Position)
            .filter(Position.account_id == account_id, Position.asset_code == asset_code)
            .order_by(Position.snapshot_date.desc())
            .first()
        )

        if existing is None:
            new_positions.append({
                "asset_code": asset_code,
                "ai_quantity": ai_qty,
                "level": "new",
            })
            continue

        db_qty = float(existing.quantity)
        if db_qty == 0:
            # Can't compute percentage diff — treat as new if AI also shows quantity
            if ai_qty != 0:
                new_positions.append({
                    "asset_code": asset_code,
                    "ai_quantity": ai_qty,
                    "db_quantity": db_qty,
                    "level": "new",
                })
            continue

        diff_pct = abs(ai_qty - db_qty) / abs(db_qty)
        item = {
            "asset_code":  asset_code,
            "ai_quantity": ai_qty,
            "db_quantity": db_qty,
            "diff_pct":    round(diff_pct * 100, 1),
        }

        if diff_pct > _ERROR_THRESHOLD:
            item["level"] = "error"
            errors.append(item)
            logger.warning(
                "Validation ERROR %s: ai=%.2f db=%.2f diff=%.1f%%",
                asset_code, ai_qty, db_qty, diff_pct * 100,
            )
        elif diff_pct > _WARN_THRESHOLD:
            item["level"] = "warning"
            warnings.append(item)

    total = len(positions)
    matched = total - len(errors) - len(warnings) - len(new_positions)

    return {
        "errors":        errors,
        "warnings":      warnings,
        "new_positions": new_positions,
        "can_auto_confirm": len(errors) == 0,
        "summary": {
            "total":    total,
            "matched":  max(matched, 0),
            "warnings": len(warnings),
            "errors":   len(errors),
            "new":      len(new_positions),
        },
    }
