


---

# ✅ Codex任务列表（V1开发执行清单）

```
Project: Fund Management System V1

Goal:
Implement V1 system based on spec_v2.md

Rules:
- Follow nav_rules.md strictly
- Do not change database schema without approval
- Use UTC date
- NAV snapshot is immutable
- PostgreSQL only
- FastAPI backend
- Next.js frontend
- No AI in V1
- No cloud in V1
```

---

# MILESTONE 1 — Database Schema

目标：完成所有表结构

Tasks:

```
Create db/schema.sql

Tables:

Fund
Client
Holding
Account
Position
Transaction
ImportBatch
ExchangeRate
AssetPrice
NAVRecord
AssetSnapshot
ShareTransaction
FeeRecord
```

要求：

```
- Use PostgreSQL
- Add primary keys
- Add foreign keys
- Add indexes
- Add created_at
- Add updated_at
- NAVRecord must have is_locked
```

完成后：

```
Run migration
Verify tables exist
```

---

# MILESTONE 2 — Backend Project Init

目标：创建 FastAPI 项目

Tasks:

```
Create backend/

backend/app/main.py
backend/app/db.py
backend/app/models/
backend/app/api/
backend/app/services/
backend/app/core/
```

要求：

```
Use FastAPI
Use SQLAlchemy
Use Pydantic
Use Alembic
```

完成后：

```
Server runs
DB connects
```

---

# MILESTONE 3 — Models

目标：ORM模型

Tasks:

```
Fund model
Client model
Account model
Position model
Transaction model
ExchangeRate model
AssetPrice model
NAVRecord model
AssetSnapshot model
ShareTransaction model
FeeRecord model
ImportBatch model
```

要求：

```
Match schema.sql
Do not change schema
```

---

# MILESTONE 4 — Import Parser

目标：对账单解析

Tasks:

```
Create parser module

services/parser/
  ib_parser.py
  kraken_parser.py
  moomoo_parser.py
  schwab_parser.py
```

功能：

```
read csv
map fields
return normalized data
```

字段：

```
date
asset_code
quantity
price
currency
type
fee
```

完成后：

```
ImportBatch created
Transactions saved
```

---

# MILESTONE 5 — Exchange Rate Service

目标：汇率快照

Tasks:

```
services/exchange_rate.py
```

功能：

```
fetch frankfurter
save snapshot
```

要求：

```
store snapshot_date
no overwrite
```

API:

```
POST /rates/fetch
GET /rates
```

---

# MILESTONE 6 — Asset Price Snapshot

目标：价格快照

Tasks:

```
services/price_service.py
```

功能：

```
fetch yfinance
fetch coingecko
save snapshot
```

字段：

```
asset_code
price_usd
snapshot_date
```

API:

```
POST /price/fetch
```

---

# MILESTONE 7 — NAV Engine

目标：核心核算

Tasks:

```
services/nav_engine.py
```

流程：

```
load positions
load price snapshot
load fx snapshot
convert to USD
sum assets
divide shares
create NAVRecord
create AssetSnapshot
lock record
```

要求：

```
use snapshot only
no realtime
```

API:

```
POST /nav/calc
GET /nav
```

---

# MILESTONE 8 — Share Transaction

目标：申购赎回

Tasks:

```
services/share_service.py
```

功能：

```
subscribe
redeem
update shares
record history
```

规则：

```
quarter only
use nav_at_date
```

API:

```
POST /share/subscribe
POST /share/redeem
GET /share/history
```

---

# MILESTONE 9 — Performance Fee

目标：业绩报酬

Tasks:

```
services/fee_service.py
```

规则：

```
yearly
>15%
30%
deduct nav
create FeeRecord
```

API:

```
POST /fee/calc
GET /fee
```

---

# MILESTONE 10 — API Layer

目标：REST API

Tasks:

```
/fund
/client
/account
/position
/transaction
/nav
/share
/fee
/rate
/price
/import
```

要求：

```
CRUD
pagination
validation
```

---

# MILESTONE 11 — Frontend Init

目标：Next.js

Tasks:

```
frontend/
pages/
components/
lib/api.ts
```

页面：

```
dashboard
nav
accounts
import
clients
shares
```

---

# MILESTONE 12 — Dashboard

显示：

```
AUM
NAV history
asset allocation
```

---

# MILESTONE 13 — Client View

显示：

```
shares
value
return
nav history
transactions
```

---

# MILESTONE 14 — Manual NAV Flow

流程：

```
upload statement
import
fetch fx
fetch price
calc nav
lock nav
```

必须能完整跑通。

---

# MILESTONE 15 — Final Test

测试：

```
real csv
real nav
real fee
real share
```

必须验证：

```
nav correct
share correct
fee correct
snapshot correct
```




