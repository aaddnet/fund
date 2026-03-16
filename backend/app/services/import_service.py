from datetime import UTC, datetime
from app.models import ImportBatch, Transaction
from app.services.parser import ib_parser, kraken_parser, moomoo_parser, schwab_parser

PARSERS = {
    "ib": ib_parser,
    "kraken": kraken_parser,
    "moomoo": moomoo_parser,
    "schwab": schwab_parser,
}


def import_statement(db, source: str, path: str, account_id: int):
    parser = PARSERS[source]
    rows = parser.parse(path)
    batch = ImportBatch(source=source, filename=path, imported_at=datetime.now(UTC))
    db.add(batch)
    db.flush()
    for r in rows:
        db.add(Transaction(account_id=account_id, trade_date=r["date"], asset_code=r["asset_code"], quantity=r["quantity"], price=r["price"], currency=r["currency"], tx_type=r["type"], fee=r["fee"], import_batch_id=batch.id))
    db.commit()
    return batch
