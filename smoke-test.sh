#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3000}"
AUTH_USER="${AUTH_USER:-ops}"
AUTH_PASSWORD="${AUTH_PASSWORD:-Ops1234567}"
DB_CONTAINER="${DB_CONTAINER:-invest_local_db}"

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

login() {
  curl -fsS -X POST "$BASE_URL/auth/login" \
    -F "username=$AUTH_USER" \
    -F "password=$AUTH_PASSWORD"
}

TOKEN="$(login | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
AUTH_HEADER=( -H "Authorization: Bearer $TOKEN" )

# Admin token used for write operations that require admin role (client/account CRUD)
ADMIN_TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/login" -F 'username=admin' -F 'password=Admin12345' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
ADMIN_HEADER=( -H "Authorization: Bearer $ADMIN_TOKEN" )

echo "== Health checks =="
curl -fsS "$BASE_URL/health" && echo
curl -fsS "$BASE_URL/health/db" && echo

echo "== Who am I =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/auth/me" && echo

echo "== Seed demo data =="
cat <<'SQL' | docker exec -i "$DB_CONTAINER" psql -U fund_user -d fund_system >/dev/null
INSERT INTO fund (id, name, base_currency, total_shares) VALUES (1, 'Demo Fund', 'USD', 0) ON CONFLICT (id) DO UPDATE SET total_shares = EXCLUDED.total_shares;
INSERT INTO client (id, name, email) VALUES (1, 'Alice', 'alice@example.com') ON CONFLICT (id) DO NOTHING;
INSERT INTO account (id, fund_id, client_id, broker, account_no) VALUES (1, 1, 1, 'IB', 'ACC-001') ON CONFLICT (id) DO NOTHING;
INSERT INTO account (id, fund_id, client_id, broker, account_no) VALUES (2, 1, 1, 'HK Broker', 'ACC-HKD-01') ON CONFLICT (id) DO NOTHING;
SELECT setval('client_id_seq', (SELECT MAX(id) FROM client));
SELECT setval('account_id_seq', (SELECT MAX(id) FROM account));
SELECT setval('fund_id_seq', (SELECT MAX(id) FROM fund));
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
IMPORT_BATCH_ID="$(curl -fsS -X POST "$BASE_URL/import/upload" "${AUTH_HEADER[@]}" -F "source=csv" -F "account_id=1" -F "file=@$TMP_CSV;type=text/csv" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/import/$IMPORT_BATCH_ID" && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" "$BASE_URL/import/$IMPORT_BATCH_ID/confirm" && echo

echo "== Client / Account CRUD flow =="
# Client and account creation requires admin role
NEW_CLIENT_ID="$(curl -fsS -X POST "${ADMIN_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/client" -d '{"name":"Bob", "email":"bob@example.com"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "Created Client ID: $NEW_CLIENT_ID"
NEW_ACCOUNT_ID="$(curl -fsS -X POST "${ADMIN_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/account" -d "{\"fund_id\":1, \"client_id\":$NEW_CLIENT_ID, \"broker\":\"TestBroker\", \"account_no\":\"TEST-$RANDOM\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "Created Account ID: $NEW_ACCOUNT_ID"
curl -fsS -X PATCH "${ADMIN_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/client/$NEW_CLIENT_ID" -d '{"name":"Bob Updated"}' && echo
curl -fsS -X PATCH "${ADMIN_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/account/$NEW_ACCOUNT_ID" -d '{"broker":"TestBroker Updated"}' && echo

echo "== Business flow =="
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/nav/calc" -d '{"fund_id":1,"nav_date":"2026-03-31"}' && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/nav/calc" -d '{"fund_id":1,"nav_date":"2026-06-30"}' && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/share/subscribe" -d '{"fund_id":1,"client_id":1,"tx_date":"2026-06-30","amount_usd":500}' && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/share/redeem" -d '{"fund_id":1,"client_id":1,"tx_date":"2026-06-30","amount_usd":200}' && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/fee/calc" -d '{"fund_id":1,"fee_date":"2026-09-30"}' && echo

echo "== Scheduler + audit =="
curl -fsS -X POST "${AUTH_HEADER[@]}" "$BASE_URL/scheduler/jobs/fx-weekly/run" && echo
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/scheduler/jobs?limit=10" && echo
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/audit?limit=20" && echo

echo "== Client readonly boundary =="
CLIENT_TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/login" -F 'username=client1' -F 'password=Client12345' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
curl -fsS -H "Authorization: Bearer $CLIENT_TOKEN" "$BASE_URL/customer/1" && echo
STATUS_CODE="$(curl -sS -o /tmp/invest-customer-2-denied.txt -w '%{http_code}' -H "Authorization: Bearer $CLIENT_TOKEN" "$BASE_URL/customer/2")"
if [[ "$STATUS_CODE" != "403" ]]; then
  echo "Expected client-readonly access to other customer to be forbidden" >&2
  exit 1
fi

echo "== Frontend =="
curl -fsSI "$WEB_URL" | sed -n '1,8p'

echo "Smoke test completed successfully."
