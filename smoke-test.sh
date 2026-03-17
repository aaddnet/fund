#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3000}"
DB_CONTAINER="${DB_CONTAINER:-fund_system_db}"

TMP_CSV="$(mktemp /tmp/invest-import-XXXXXX.csv)"
cat > "$TMP_CSV" <<'CSV'
trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date
2026-03-31,AAPL,10,200,USD,buy,1,2026-03-31
2026-03-31,BTC,0.5,80000,USD,buy,2,2026-03-31
CSV

cleanup() {
  rm -f "$TMP_CSV"
}
trap cleanup EXIT

echo "== Health checks =="
curl -fsS "$BASE_URL/health" | tee /tmp/invest-health.json && echo
curl -fsS "$BASE_URL/health/db" | tee /tmp/invest-health-db.json && echo

echo "== Seed demo data =="
cat <<'SQL' | docker exec -i "$DB_CONTAINER" psql -U fund_user -d fund_system >/dev/null
INSERT INTO fund (id, name, base_currency, total_shares) VALUES (1, 'Demo Fund', 'USD', 1000) ON CONFLICT (id) DO NOTHING;
INSERT INTO client (id, name, email) VALUES (1, 'Alice', 'alice@example.com') ON CONFLICT (id) DO NOTHING;
INSERT INTO account (id, fund_id, client_id, broker, account_no) VALUES (1, 1, 1, 'IB', 'ACC-001') ON CONFLICT (id) DO NOTHING;
INSERT INTO position (account_id, asset_code, quantity, average_cost, currency, snapshot_date)
VALUES
  (1, 'AAPL', 10, 150, 'USD', DATE '2026-03-31'),
  (1, 'BTC', 0.5, 60000, 'USD', DATE '2026-03-31'),
  (1, 'AAPL', 10, 150, 'USD', DATE '2026-06-30'),
  (1, 'BTC', 0.5, 60000, 'USD', DATE '2026-06-30')
ON CONFLICT DO NOTHING;
INSERT INTO asset_price (asset_code, price_usd, source, snapshot_date)
VALUES
  ('AAPL', 200, 'seed', DATE '2026-03-31'),
  ('BTC', 80000, 'seed', DATE '2026-03-31'),
  ('AAPL', 220, 'seed', DATE '2026-06-30'),
  ('BTC', 90000, 'seed', DATE '2026-06-30')
ON CONFLICT (asset_code, snapshot_date) DO NOTHING;
SQL

echo "== Import flow =="
curl -fsS -X POST "$BASE_URL/import/upload" \
  -F "source=csv" \
  -F "account_id=1" \
  -F "file=@$TMP_CSV;type=text/csv" | tee /tmp/invest-import-upload.json && echo
IMPORT_BATCH_ID="$(python3 - <<'PY'
import json
with open('/tmp/invest-import-upload.json') as fh:
    data = json.load(fh)
print(data['id'])
PY
)"
curl -fsS "$BASE_URL/import/$IMPORT_BATCH_ID" | tee /tmp/invest-import-detail.json && echo
curl -fsS -X POST "$BASE_URL/import/$IMPORT_BATCH_ID/confirm" | tee /tmp/invest-import-confirm.json && echo

echo "== Business flow =="
curl -fsS -X POST "$BASE_URL/nav/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"nav_date":"2026-03-31"}' | tee /tmp/invest-nav1.json && echo
curl -fsS -X POST "$BASE_URL/nav/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"nav_date":"2026-06-30"}' | tee /tmp/invest-nav2.json && echo
curl -fsS "$BASE_URL/nav" | tee /tmp/invest-nav-list.json && echo
curl -fsS -X POST "$BASE_URL/share/subscribe" -H 'Content-Type: application/json' -d '{"fund_id":1,"client_id":1,"tx_date":"2026-06-30","amount_usd":500}' | tee /tmp/invest-share.json && echo
curl -fsS "$BASE_URL/share/history" | tee /tmp/invest-share-history.json && echo
curl -fsS -X POST "$BASE_URL/fee/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"fee_date":"2026-09-30"}' | tee /tmp/invest-fee.json && echo
curl -fsS "$BASE_URL/fee" | tee /tmp/invest-fee-list.json && echo

echo "== Frontend =="
curl -fsSI "$WEB_URL" | sed -n '1,8p'

echo "Smoke test completed successfully."
