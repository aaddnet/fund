import csv
import io
from pathlib import Path


def parse_csv(path: str):
    """Legacy file-path based parser for standalone use."""
    rows = []
    with Path(path).open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "date": row.get("date"),
                    "asset_code": row.get("asset_code"),
                    "quantity": float(row.get("quantity", 0) or 0),
                    "price": float(row.get("price", 0) or 0),
                    "currency": row.get("currency", "USD"),
                    "type": row.get("type", "trade"),
                    "fee": float(row.get("fee", 0) or 0),
                }
            )
    return rows


def preprocess(raw: bytes) -> bytes:
    """Identity preprocessor — returns raw bytes unchanged (generic CSV)."""
    return raw
