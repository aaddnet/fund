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
INSERT INTO fund (id, name, base_currency, total_shares) VALUES (1, 'Demo Fund', 'USD', 0) ON CONFLICT (id) DO UPDATE SET total_shares = EXCLUDED.total_shares;
INSERT INTO client (id, name, email) VALUES (1, 'Alice', 'alice@example.com') ON CONFLICT (id) DO NOTHING;
INSERT INTO account (id, fund_id, client_id, broker, account_no) VALUES (1, 1, 1, 'IB', 'ACC-001') ON CONFLICT (id) DO NOTHING;
INSERT INTO account (id, fund_id, client_id, broker, account_no) VALUES (2, 1, 1, 'HK Broker', 'ACC-HKD-01') ON CONFLICT (id) DO NOTHING;
INSERT INTO position (account_id, asset_code, quantity, average_cost, currency, snapshot_date)
VALUES
  (1, 'AAPL', 10, 150, 'USD', DATE '2026-03-31'),
  (1, 'BTC', 0.5, 60000, 'USD', DATE '2026-03-31'),
  (2, '0700.HK', 100, 300, 'HKD', DATE '2026-03-31'),
  (1, 'AAPL', 10, 150, 'USD', DATE '2026-06-30'),
  (1, 'BTC', 0.5, 60000, 'USD', DATE '2026-06-30'),
  (2, '0700.HK', 120, 320, 'HKD', DATE '2026-06-30')
ON CONFLICT DO NOTHING;
INSERT INTO asset_price (asset_code, price_usd, source, snapshot_date)
VALUES
  ('AAPL', 200, 'seed', DATE '2026-03-31'),
  ('BTC', 80000, 'seed', DATE '2026-03-31'),
  ('AAPL', 220, 'seed', DATE '2026-06-30'),
  ('BTC', 90000, 'seed', DATE '2026-06-30')
ON CONFLICT (asset_code, snapshot_date) DO NOTHING;
INSERT INTO exchange_rate (base_currency, quote_currency, rate, snapshot_date)
VALUES
  ('HKD', 'USD', 0.12820513, DATE '2026-03-31'),
  ('HKD', 'USD', 0.12700000, DATE '2026-06-30')
ON CONFLICT (base_currency, quote_currency, snapshot_date) DO NOTHING;
DELETE FROM share_transaction WHERE fund_id = 1;
DELETE FROM fee_record WHERE fund_id = 1;
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
curl -fsS -H 'x-dev-role: ops' "$BASE_URL/import/$IMPORT_BATCH_ID" | tee /tmp/invest-import-detail.json && echo
curl -fsS -X POST -H 'x-dev-role: ops' -H 'x-operator-id: smoke' "$BASE_URL/import/$IMPORT_BATCH_ID/confirm" | tee /tmp/invest-import-confirm.json && echo

echo "== Read APIs =="
curl -fsS "$BASE_URL/fund?page=1&size=10" | tee /tmp/invest-funds.json && echo
curl -fsS "$BASE_URL/account?page=1&size=10&fund_id=1" | tee /tmp/invest-accounts.json && echo
curl -fsS "$BASE_URL/position?page=1&size=10&fund_id=1&snapshot_date=2026-03-31" | tee /tmp/invest-positions.json && echo
curl -fsS "$BASE_URL/transaction?page=1&size=10&fund_id=1" | tee /tmp/invest-transactions.json && echo

echo "== Business flow =="
curl -fsS -X POST "$BASE_URL/nav/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"nav_date":"2026-03-31"}' | tee /tmp/invest-nav1.json && echo
curl -fsS -X POST "$BASE_URL/nav/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"nav_date":"2026-06-30"}' | tee /tmp/invest-nav2.json && echo
curl -fsS "$BASE_URL/nav" | tee /tmp/invest-nav-list.json && echo
curl -fsS -X POST "$BASE_URL/share/subscribe" -H 'Content-Type: application/json' -d '{"fund_id":1,"client_id":1,"tx_date":"2026-06-30","amount_usd":500}' | tee /tmp/invest-share-subscribe.json && echo
curl -fsS -X POST "$BASE_URL/share/redeem" -H 'Content-Type: application/json' -d '{"fund_id":1,"client_id":1,"tx_date":"2026-06-30","amount_usd":200}' | tee /tmp/invest-share-redeem.json && echo
curl -fsS "$BASE_URL/share/history?fund_id=1&client_id=1" | tee /tmp/invest-share-history.json && echo
curl -fsS "$BASE_URL/share/balances?fund_id=1" | tee /tmp/invest-share-balances.json && echo
curl -fsS -X POST "$BASE_URL/fee/calc" -H 'Content-Type: application/json' -d '{"fund_id":1,"fee_date":"2026-09-30"}' | tee /tmp/invest-fee.json && echo
curl -fsS "$BASE_URL/fee" | tee /tmp/invest-fee-list.json && echo

echo "== Frontend =="
curl -fsSI "$WEB_URL" | sed -n '1,8p'

echo "Smoke test completed successfully."
 successfully."
09-30"}' | tee /tmp/invest-fee.json && echo
curl -fsS -H 'x-dev-role: ops' "$BASE_URL/fee" | tee /tmp/invest-fee-list.json && echo

echo "== Scheduler and audit =="
curl -fsS -X POST "$BASE_URL/scheduler/jobs/fx-weekly/run" -H 'x-dev-role: ops' -H 'x-operator-id: smoke' | tee /tmp/invest-scheduler-run.json && echo
curl -fsS -H 'x-dev-role: ops' "$BASE_URL/scheduler/jobs?limit=10" | tee /tmp/invest-scheduler-jobs.json && echo
curl -fsS -H 'x-dev-role: ops' "$BASE_URL/audit?limit=20" | tee /tmp/invest-audit.json && echo


echo "== Client readonly boundary =="
curl -fsS -H 'x-dev-role: client-readonly' -H 'x-client-id: 1' "$BASE_URL/customer/1" | tee /tmp/invest-customer-1.json && echo
curl -sS -o /tmp/invest-customer-2-denied.txt -w '%{http_code}' -H 'x-dev-role: client-readonly' -H 'x-client-id: 1' "$BASE_URL/customer/2" | tee /tmp/invest-customer-2-code.txt && echo
if [[ "$(cat /tmp/invest-customer-2-code.txt)" != "403" ]]; then
  echo "Expected client-readonly access to other customer to be forbidden" >&2
  exit 1
fi

echo "== Frontend =="
curl -fsSI "$WEB_URL" | sed -n '1,8p'

echo "Smoke test completed successfully."
