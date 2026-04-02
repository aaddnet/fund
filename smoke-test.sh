#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3000}"
AUTH_USER="${AUTH_USER:-admin}"
AUTH_PASSWORD="${AUTH_PASSWORD:-Admin12345}"

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
curl -fsS "$BASE_URL/health" && echo
curl -fsS "$BASE_URL/health/db" && echo

echo "== Login =="
TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/login" \
  -F "username=$AUTH_USER" \
  -F "password=$AUTH_PASSWORD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
AUTH_HEADER=( -H "Authorization: Bearer $TOKEN" )

echo "== Who am I =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/auth/me" && echo

echo "== Account CRUD =="
ACCOUNT_ID="$(curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/account" \
  -d '{"broker":"IB","account_no":"SMOKE-TEST-'$RANDOM'","holder_name":"Smoke Test"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "Created Account ID: $ACCOUNT_ID"
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/account/$ACCOUNT_ID" && echo

echo "== Import flow =="
IMPORT_BATCH_ID="$(curl -fsS -X POST "$BASE_URL/import/upload" "${AUTH_HEADER[@]}" \
  -F "source=csv" -F "account_id=$ACCOUNT_ID" -F "file=@$TMP_CSV;type=text/csv" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "Import Batch ID: $IMPORT_BATCH_ID"
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/import/$IMPORT_BATCH_ID" && echo
curl -fsS -X POST "${AUTH_HEADER[@]}" "$BASE_URL/import/$IMPORT_BATCH_ID/confirm" && echo

echo "== Transactions =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/transaction?page=1&size=5&account_id=$ACCOUNT_ID" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Transactions: {d[\"pagination\"][\"total\"]}")'

echo "== Cash balance =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/cash/balance?account_id=$ACCOUNT_ID" && echo

echo "== Positions =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/position?account_id=$ACCOUNT_ID" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Positions: {d[\"pagination\"][\"total\"]}")'

echo "== NAV calculation =="
curl -fsS -X POST "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' "$BASE_URL/nav/calc" \
  -d '{"nav_date":"2026-03-31"}' && echo

echo "== Rates + Prices =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/rates?page=1&size=5" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Rates: {d[\"pagination\"][\"total\"]}")'
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/price?page=1&size=5" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Prices: {d[\"pagination\"][\"total\"]}")'

echo "== Scheduler + Audit =="
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/scheduler/jobs?limit=5" && echo
curl -fsS "${AUTH_HEADER[@]}" "$BASE_URL/audit?limit=5" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Audit entries: {len(d)}")'

echo "== Frontend =="
curl -fsSI "$WEB_URL" | sed -n '1,5p'

echo ""
echo "Smoke test completed successfully."
