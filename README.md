# Fund - Investment Portfolio Tracker

Self-hosted investment portfolio tracker with multi-broker CSV import, multi-currency support, and automated portfolio valuation.

## Features

- **Multi-Broker Import** - Parse and import CSV/statements from Interactive Brokers, Futu/Moomoo, Charles Schwab, Kraken
- **Multi-Currency** - Track positions and cash across USD, HKD, CNH, EUR, GBP with FX rate management
- **Portfolio Valuation** - Calculate total portfolio value (NAV) with asset price lookups and FX conversion
- **Cash Ledger** - Automatic cash balance tracking derived from transactions (deposits, withdrawals, dividends, interest, fees)
- **Transaction Management** - Full CRUD for trades, dividends, fees, FX, corporate actions with fee decomposition
- **Bilingual UI** - Chinese and English interface
- **Role-Based Access** - Admin (full access) and Readonly roles with session-based auth

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (TypeScript, SSR) |
| Backend | FastAPI (Python 3.12, SQLAlchemy 2.x) |
| Database | PostgreSQL 16 |
| Migration | Alembic |
| Deploy | Docker Compose |

## Quick Start

### Docker (Recommended)

```bash
# Clone and start
git clone https://github.com/aaddnet/fund.git
cd fund

# Start all services
docker compose -f docker-compose.local.yml up -d

# Access
# Frontend: http://127.0.0.1:3000
# Backend:  http://127.0.0.1:8000
```

Default admin credentials: `admin / Admin12345`

### Environment Variables

Copy `.env.example` to `.env.local` and customize:

```env
DATABASE_URL=postgresql://fund_user:fund_pass@db:5432/fund_system
AUTH_SECRET_KEY=change-me-to-a-random-64-char-secret
AUTH_ENABLED=true
AUTH_BOOTSTRAP_USERS_JSON=[{"username":"admin","password":"YourStrongPassword123","role":"admin"}]
```

## Architecture

```
Browser ──3000──▶ Frontend (Next.js SSR)
                      │
                      │ INTERNAL_API_BASE
                      ▼
                  Backend (FastAPI)
                      │
                      │ DATABASE_URL
                      ▼
                  PostgreSQL 16
```

## Data Model

| Table | Purpose |
|-------|---------|
| `account` | Brokerage accounts (broker, account_no, holder) |
| `transaction` | All trades, cash movements, dividends, fees, FX |
| `position` | Asset position snapshots per account |
| `cash_position` | Cash balance snapshots per currency |
| `import_batch` | CSV import tracking with preview and confirmation |
| `asset_price` | Asset prices for NAV calculation |
| `exchange_rate` | FX rates for multi-currency conversion |
| `nav_record` | Portfolio valuation snapshots |
| `asset_snapshot` | Per-asset valuation details within NAV |
| `auth_user` | User accounts with role-based permissions |
| `auth_session` | Session tokens for authentication |
| `audit_log` | Action audit trail |

## API Overview

| Group | Endpoints | Description |
|-------|-----------|-------------|
| Auth | `POST /auth/login`, `/auth/me`, `/auth/users` | Login, session management, user CRUD |
| Accounts | `GET/POST /account` | Brokerage account management |
| Transactions | `GET/POST/PATCH/DELETE /transaction` | Trade and cash movement CRUD |
| Import | `POST /import/upload`, `/import/{id}/confirm` | CSV upload, preview, and confirmation |
| Cash | `GET /cash/balance`, `/cash/flow` | Cash balances and flow history |
| NAV | `POST /nav/calc`, `GET /nav` | Portfolio valuation calculation |
| Prices | `GET/POST /price` | Asset price management |
| Rates | `GET/POST /rates` | FX rate management |
| Reports | `GET /reports/overview`, `/reports/export` | Portfolio reports and CSV export |

## Supported Brokers

| Broker | Format | Features |
|--------|--------|----------|
| Interactive Brokers | Activity Statement (CSV) | Trades, dividends, interest, fees, FX, transfers |
| Futu / Moomoo | Trade CSV (Chinese headers) | Trades with partial-fill merging, fee decomposition |
| Charles Schwab | Transaction CSV | Trades, dividends, transfers |
| Kraken | Trade/Ledger CSV | Crypto trades |

## Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/dashboard` | System health, NAV trend, recent activity |
| Accounts | `/accounts` | Account list with broker filter |
| Portfolio Value | `/nav` | NAV calculation and history |
| Transactions | `/transactions` | Transaction list with filters |
| CSV Import | `/import` | Upload, preview, and confirm CSV imports |
| Cash Ledger | `/cash` | Cash balance summary and flow history |
| Reports | `/reports` | Portfolio overview reports |
| Settings | `/settings` | User management, FX rates, asset prices |

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database Migration

```bash
cd backend
alembic upgrade head
```

## License

MIT
