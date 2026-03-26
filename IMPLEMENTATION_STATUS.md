# V1 Implementation Status

Implemented milestones from `implement_v1.md`:

1. Database schema in `db/schema.sql` with PK/FK/indexes/timestamps and `nav_record.is_locked`.
2. FastAPI project scaffold with SQLAlchemy/Pydantic/Alembic baseline.
3. ORM models matching schema.
4. Statement parser modules for IB/Kraken/Moomoo/Schwab and import service.
5. Exchange rate snapshot service (Frankfurter) and `/rates` APIs.
6. Asset price snapshot service (yfinance/CoinGecko) and `/price/fetch` API.
7. NAV engine (`/nav/calc`, `/nav`) with locked NAV + asset snapshots.
8. Share transaction service (`/share/subscribe`, `/share/redeem`, `/share/history`, `/share/balances`) with quarter-month guard, balance derivation, and over-redemption validation.
9. Performance fee service (`/fee/calc`, `/fee`) with richer fee record fields aligned to V1 business notes.
10. API layer includes required route families with placeholders for CRUD/pagination shape.
11-13. Next.js frontend initialized with dashboard/nav/accounts/import/clients/shares pages.
14. Manual NAV workflow components implemented across import/rate/price/nav services.
15. Shares page now supports real subscribe/redeem flows and displays current balances.
16. Basic compile checks + smoke script coverage updated in current environment.
17. Week 3 read workflow uplift: accounts and clients pages now support backend-driven filters and richer read-only operational details.
18. Minimal customer read-only view added via `/customer/{client_id}` backend API and `/customers/[clientId]` frontend route.
19. Basic reporting/query capability added via `/reports/overview` and `/reports` with month/quarter/year plus fund/client filters.
20. Week 4 scheduler support added with APScheduler-backed local job registration, weekly FX fetch, manual trigger endpoint, and persisted scheduler run logs (`/scheduler/jobs`, `/scheduler/jobs/fx-weekly/run`).
21. Minimal explicit auth boundary added for internal testing via header/query-based dev auth (`admin`, `ops`, `client-readonly`). Client-readonly requests are constrained to their own client scope in intended read flows.
22. Audit trail uplift added for important operational actions including import upload/confirm, NAV calc, fee calc, manual scheduler trigger, and share subscribe/redeem. Read-only audit inspection is exposed via `/audit`.
23. Validation coverage strengthened with smoke test updates plus lightweight API tests for auth scope, audit write, manual scheduler run, and redeem failure handling.

## Internal test ready notes

- Dev auth defaults to enabled and uses headers like `x-dev-role`, `x-client-id`, and `x-operator-id`.
- Scheduler defaults to enabled and is intended for local/dev single-process usage for now.
- Client-readonly is intentionally minimal: it is a boundary for intended flows, not full production auth.
- Runtime compatibility helpers in `app/main.py` still support older local DBs without forcing full migrations.
