# V1 Implementation Status

Implemented milestones from `implement_v1.md`:

1. Database schema in `db/schema.sql` with PK/FK/indexes/timestamps and `nav_record.is_locked`.
2. FastAPI project scaffold with SQLAlchemy/Pydantic/Alembic baseline.
3. ORM models matching schema.
4. Statement parser modules for IB/Kraken/Moomoo/Schwab and import service.
5. Exchange rate snapshot service (Frankfurter) and `/rates` APIs.
6. Asset price snapshot service (yfinance/CoinGecko) and `/price/fetch` API.
7. NAV engine (`/nav/calc`, `/nav`) with locked NAV + asset snapshots.
8. Share transaction service (`/share/subscribe`, `/share/redeem`, `/share/history`) with quarter-month guard.
9. Performance fee service (`/fee/calc`, `/fee`).
10. API layer includes required route families with placeholders for CRUD/pagination shape.
11-13. Next.js frontend initialized with dashboard/nav/accounts/import/clients/shares pages.
14. Manual NAV workflow components implemented across import/rate/price/nav services.
15. Basic compile checks completed in current environment.
