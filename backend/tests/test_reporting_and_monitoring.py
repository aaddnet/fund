from datetime import date

from app.models import ShareTransaction, Transaction


def test_reports_overview_returns_breakdowns_and_series(client, seeded_db, auth_headers):
    seeded_db.add(Transaction(account_id=1, trade_date=date(2026, 6, 30), asset_code='AAPL', quantity=2, price=150, currency='USD', tx_type='buy', fee=1))
    seeded_db.add(Transaction(account_id=1, trade_date=date(2026, 6, 30), asset_code='MSFT', quantity=1, price=300, currency='USD', tx_type='buy', fee=1))
    seeded_db.commit()

    response = client.get('/reports/overview', headers=auth_headers, params={'period_value': '2026-Q2'})
    assert response.status_code == 200
    payload = response.json()

    assert payload['summary']['fund_count'] >= 1
    assert payload['summary']['client_count'] >= 1
    assert 'breakdowns' in payload
    assert payload['breakdowns']['by_fund']
    assert payload['breakdowns']['transactions_by_asset']
    assert payload['series']['share_flow_by_date']
    assert payload['series']['nav_trend']


def test_reports_overview_supports_tx_type_filter(client, seeded_db, auth_headers):
    seeded_db.add(ShareTransaction(fund_id=1, client_id=1, tx_date=date(2026, 6, 30), tx_type='redeem', amount_usd=25, shares=2.5, nav_at_date=10))
    seeded_db.commit()

    response = client.get('/reports/overview', headers=auth_headers, params={'period_value': '2026-Q2', 'tx_type': 'redeem'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['summary']['share_tx_count'] == 1
    assert all(item['tx_type'] == 'redeem' for item in payload['share_history'])


def test_metrics_and_readiness_endpoints_are_available(client, seeded_db):
    assert client.get('/health/live').status_code == 200
    assert client.get('/health/ready').status_code == 200

    metrics_response = client.get('/metrics')
    assert metrics_response.status_code == 200
    assert 'invest_http_requests_total' in metrics_response.text

    json_response = client.get('/metrics/json')
    assert json_response.status_code == 200
    payload = json_response.json()
    assert 'uptime_seconds' in payload
    assert 'routes' in payload
