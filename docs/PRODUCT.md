# Invest - 基金管理系统 产品架构文档

> V1 内部测试版 | 2026-03-30

---

## 1. 产品概述

Invest 是一套面向私募基金运营的内部管理平台，涵盖基金全生命周期管理：从创建基金、导入券商数据、计算净值，到份额申赎、客户资本账户和报表导出。

**目标用户**：基金管理人 (GP)、运营团队、客户关系经理、投资者（只读视图）。

**核心能力**：
- 多基金、多账户、多币种管理
- 券商交易数据批量导入（IB、Kraken、Schwab、Moomoo）
- 自动化 NAV（净值）计算，含现金头寸
- 份额申购/赎回/种子资本，配套台账与资本账户
- 绩效费计算（超额收益 hurdle rate 模型）
- 5 级 RBAC 权限体系
- 中英文双语界面

**技术栈**：

| 层 | 技术 |
|---|---|
| 前端 | Next.js 14 (TypeScript, SSR) |
| 后端 | FastAPI (Python 3.12, SQLAlchemy 2.x) |
| 数据库 | PostgreSQL 16 |
| 迁移 | Alembic |
| 部署 | Docker Compose |

---

## 2. 系统架构

```
                    ┌─────────────────────────────────────────┐
                    │              Docker Compose              │
                    │                                         │
  Browser ──3000──▶ │  frontend (Next.js 14 SSR)              │
                    │       │                                 │
                    │       │ INTERNAL_API_BASE (http://backend:8000)
                    │       ▼                                 │
                    │  backend (FastAPI + Uvicorn)             │
                    │       │                                 │
                    │       │ DATABASE_URL                    │
                    │       ▼                                 │
                    │  db (PostgreSQL 16)                      │
                    │       │                                 │
                    │       ▼ invest_pgdata (volume)          │
                    └─────────────────────────────────────────┘
```

**请求流**：
1. 浏览器访问 `http://127.0.0.1:3000`，Next.js 通过 `getServerSideProps` 在服务端调用后端 API
2. 后端 FastAPI 处理业务逻辑，通过 SQLAlchemy ORM 操作 PostgreSQL
3. 前端将 cookie 中的 access_token 透传给后端，完成认证

**关键设计决策**：
- **SSR 优先**：所有页面数据在服务端获取，避免客户端 CORS 问题，SEO 友好
- **Token 认证**：access_token + refresh_token 双 token 机制，cookie 自动管理
- **审计日志**：所有写操作自动记录 AuditLog，含操作人、实体、详情

---

## 3. 数据模型

### 3.1 实体关系概览

```
Fund ─┬─< Account ─┬─< Position
      │             ├─< Transaction
      │             ├─< ImportBatch
      │             └─< CashPosition
      │
      ├─< NAVRecord ──< AssetSnapshot
      ├─< ShareTransaction
      ├─< ShareRegister
      ├─< ClientCapitalAccount >── Client
      ├─< FeeRecord
      │
Client ─< AuthUser (client_scope_id)
AuthUser ─< AuthSession
```

### 3.2 核心实体

#### Fund（基金）
基金主表，承载生命周期状态和费率参数。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| name | String(255) | 基金名称 |
| base_currency | String(10) | 基础货币，默认 USD |
| total_shares | Numeric(20,6) | 当前总份额 |
| fund_code | String(20) | 基金编码 |
| status | String(20) | draft / active / closed |
| inception_date | Date | 成立日期 |
| first_capital_date | Date | 首笔资金日期 |
| fund_type | String(50) | 基金类型，默认 private_equity |
| hurdle_rate | Numeric(8,4) | 门槛收益率 |
| perf_fee_rate | Numeric(8,4) | 绩效费率 |
| perf_fee_frequency | String(20) | 绩效费计算频率 |
| subscription_cycle | String(20) | 申购周期 |
| nav_decimal / share_decimal | Integer | 净值/份额小数位数，默认 6 |
| description | Text | 描述 |

#### Account（券商账户）
独立于客户的券商交易账户，holder_name 记录开户人/公司。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| fund_id | FK → Fund | 所属基金 |
| holder_name | String(200) | 持有人名称 |
| broker | String(100) | 券商 |
| account_no | String(100) | 账号（fund_id + account_no 唯一） |

#### Position（持仓）
按日期快照记录每个账户的资产持仓。

| 字段 | 类型 | 说明 |
|---|---|---|
| account_id | FK → Account | |
| asset_code | String(50) | 资产代码 |
| quantity | Numeric(24,8) | 数量 |
| average_cost | Numeric(24,8) | 加权平均成本 |
| currency | String(10) | 币种 |
| snapshot_date | Date | 快照日期（account + asset + date 唯一）|

#### Transaction（交易记录）
由导入流程生成的逐笔交易。

| 字段 | 类型 | 说明 |
|---|---|---|
| account_id | FK → Account | |
| trade_date | Date | 交易日期 |
| asset_code | String(50) | |
| quantity / price | Numeric(24,8) | 数量/价格 |
| currency | String(10) | |
| tx_type | String(50) | buy / sell / trade |
| fee | Numeric(24,8) | 手续费 |
| import_batch_id | FK → ImportBatch | 来源批次 |

#### NAVRecord（净值记录）
每个基金每日一条，由 NAV 引擎计算生成。

| 字段 | 类型 | 说明 |
|---|---|---|
| fund_id | FK → Fund | |
| nav_date | Date | 净值日期（fund + date 唯一） |
| total_assets_usd | Numeric(24,8) | 总资产（持仓 + 现金） |
| total_shares | Numeric(24,8) | 总份额 |
| nav_per_share | Numeric(24,8) | 单位净值 |
| cash_total_usd | Numeric(24,8) | 现金部分 |
| positions_total_usd | Numeric(24,8) | 持仓部分 |
| is_locked | Boolean | 是否锁定 |

#### AssetSnapshot（资产快照）
NAV 计算时的持仓明细快照，按 asset_code + currency 聚合。

#### ShareTransaction（份额流水）
记录每笔申购/赎回/种子资本。

| 字段 | 类型 | 说明 |
|---|---|---|
| fund_id | FK → Fund | |
| client_id | FK → Client（可空） | |
| tx_date | Date | 交易日期 |
| tx_type | String(20) | seed / subscribe / redeem |
| amount_usd | Numeric(24,8) | 金额 |
| shares | Numeric(24,8) | 份额 |
| nav_at_date | Numeric(24,8) | 交易时单位净值 |

#### ShareRegister（份额台账）
权威份额变动登记簿，与 ShareTransaction 关联但独立维护。

| 字段 | 类型 | 说明 |
|---|---|---|
| fund_id | FK → Fund | |
| client_id | FK → Client（可空） | |
| event_date / event_type | Date / String(30) | seed / subscription / redemption / fee_deduction |
| shares_delta / shares_after | Numeric(24,8) | 变动量 / 变动后余额 |
| nav_per_share | Numeric(24,8) | 对应净值 |
| amount_usd | Numeric(24,8) | 对应金额 |
| ref_share_tx_id | FK → ShareTransaction | |

#### CashPosition（现金头寸）
按账户 + 币种 + 日期记录现金余额，参与 NAV 计算。

| 字段 | 类型 | 说明 |
|---|---|---|
| account_id | FK → Account | |
| currency | String(10) | |
| amount | Numeric(24,8) | |
| snapshot_date | Date（account + currency + date 唯一） | |

#### ClientCapitalAccount（客户资本账户）
每个客户在每个基金的投资汇总。

| 字段 | 类型 | 说明 |
|---|---|---|
| fund_id + client_id | 联合唯一 | |
| total_invested_usd | Numeric(24,8) | 累计投入 |
| total_redeemed_usd | Numeric(24,8) | 累计赎回 |
| avg_cost_nav | Numeric(24,8) | 加权平均成本净值 |
| current_shares | Numeric(24,8) | 当前持有份额 |
| unrealized_pnl_usd | Numeric(24,8) | 未实现损益 |

#### 其他实体
- **Client**：客户主表 (name, email)
- **ExchangeRate**：汇率快照 (base/quote/rate/date)
- **AssetPrice**：资产价格快照 (asset_code/price_usd/source/date)
- **FeeRecord**：绩效费记录
- **ImportBatch**：导入批次（状态：uploaded → parsed → confirmed / failed）
- **AuthUser**：系统用户 (username, password_hash, role, client_scope_id)
- **AuthSession**：会话管理 (双 token + refresh family 防重放)
- **AuditLog**：审计日志
- **SchedulerJobRun**：定时任务执行记录

### 3.3 数据库迁移

Alembic 迁移链：`0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 → 0008`

路径：`backend/alembic/versions/`

---

## 4. API 接口参考

Base URL: `http://127.0.0.1:8000`

所有接口需认证（除 `/auth/login`、`/auth/refresh`、`/auth/csrf`）。分页接口返回 `{ items: [], pagination: { page, size, total } }`。

### 4.1 认证 (Auth)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/auth/login` | 用户登录（Form: username, password） | 公开 |
| POST | `/auth/refresh` | 刷新 access_token | 公开 |
| GET | `/auth/csrf` | 获取 CSRF 配置 | 公开 |
| GET | `/auth/me` | 当前用户信息 | 已认证 |
| POST | `/auth/logout` | 注销（204） | 已认证 |
| GET | `/auth/users` | 用户列表 | auth.manage |
| POST | `/auth/users` | 创建用户 | auth.manage |
| PATCH | `/auth/users/{id}` | 更新用户 | auth.manage |
| POST | `/auth/users/{id}/reset-password` | 重置密码 | auth.manage |
| POST | `/auth/users/{id}/unlock` | 解锁用户 | auth.manage |
| PATCH | `/auth/me/password` | 修改自己密码 | 已认证 |

### 4.2 基金 (Fund)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/fund` | 基金列表（分页） | nav.read |
| GET | `/fund/{id}` | 基金详情 | nav.read |
| POST | `/fund` | 创建基金 | clients.write |
| PATCH | `/fund/{id}` | 更新基金 | clients.write |
| POST | `/fund/{id}/seed` | 录入种子资本 | clients.write |
| POST | `/fund/{id}/activate` | 激活基金 | clients.write |

### 4.3 账户 (Account)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/account` | 账户列表（分页，可按 fund_id/holder/broker/q 筛选） | accounts.read |
| GET | `/account/{id}` | 账户详情 | accounts.read |
| POST | `/account` | 创建账户 | accounts.write |
| PATCH | `/account/{id}` | 更新账户 | accounts.write |

### 4.4 持仓与交易 (Position / Transaction)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/position` | 持仓列表（分页，可按 fund_id/account_id/snapshot_date/asset_code） | accounts.read |
| GET | `/position/{id}` | 持仓详情 | accounts.read |
| GET | `/transaction` | 交易列表（分页，可按 fund_id/account_id/trade_date/import_batch_id） | accounts.read |
| GET | `/transaction/{id}` | 交易详情 | accounts.read |

### 4.5 NAV 净值

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/nav/calc` | 计算 NAV（支持 force 强制重算） | nav.write |
| GET | `/nav` | NAV 记录列表（可按 fund_id） | nav.read |
| DELETE | `/nav/{id}` | 删除 NAV 记录 | nav.write |

### 4.6 份额 (Share)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/share/subscribe` | 申购 | shares.write |
| POST | `/share/redeem` | 赎回 | shares.write |
| GET | `/share/history` | 份额流水（可按 fund_id/client_id/tx_type/date_from/date_to） | shares.read |
| GET | `/share/balances` | 份额余额 | shares.read |
| PATCH | `/share/transaction/{id}` | 编辑流水（仅 admin） | shares.write |
| DELETE | `/share/transaction/{id}` | 删除流水（仅 admin） | shares.write |
| GET | `/share/register` | 份额台账 | shares.read |
| PATCH | `/share/register/{id}` | 编辑台账（仅 admin） | clients.write |
| DELETE | `/share/register/{id}` | 删除台账（仅 admin） | clients.write |

### 4.7 现金 (Cash)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/cash` | 现金头寸列表（可按 fund_id/account_id/snapshot_date） | nav.read |
| POST | `/cash` | 新增/更新现金头寸（upsert） | nav.write |
| DELETE | `/cash/{id}` | 删除现金头寸 | nav.write |

### 4.8 数据导入 (Import)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/import` | 导入批次列表（可按 account_id） | import.read |
| GET | `/import/{id}` | 批次详情 | import.read |
| POST | `/import/upload` | 上传 CSV（Form: source, account_id, file） | import.write |
| POST | `/import/{id}/confirm` | 确认导入 | import.write |

### 4.9 客户 (Client)

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/client` | 客户列表（分页，可按 fund_id/q） | clients.read |
| GET | `/client/{id}` | 客户详情 | clients.read |
| POST | `/client` | 创建客户 | clients.write |
| PATCH | `/client/{id}` | 更新客户 | clients.write |
| GET | `/client/{id}/capital-account` | 客户资本账户 | clients.read |
| GET | `/customer/{id}` | 客户视图（含份额、NAV 聚合） | customer.read |

### 4.10 汇率与价格

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/rates/fetch` | 从外部 API 获取汇率 | rates.write |
| GET | `/rates` | 汇率列表（分页） | rates.read |
| POST | `/rates/manual` | 手动录入汇率 | rates.write |
| POST | `/price/fetch` | 获取资产价格 | price.write |
| GET | `/price` | 价格列表（分页） | price.read |

### 4.11 费用与报表

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/fee/calc` | 计算绩效费 | fees.write |
| GET | `/fee` | 费用记录列表 | fees.read |
| GET | `/reports/overview` | 报表概览（含汇总、明细、趋势） | reports.read |
| GET | `/reports/export` | 导出报表 CSV | reports.read |

### 4.12 系统

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/audit` | 审计日志 | audit.read |
| GET | `/scheduler/jobs` | 定时任务执行记录 | scheduler.read |
| POST | `/scheduler/jobs/fx-weekly/run` | 手动触发汇率任务 | scheduler.run |

---

## 5. 认证与权限

### 5.1 认证机制

- **模式**：Token 认证（AUTH_MODE=token）
- **access_token**：JWT，有效期可配置（默认 12 小时），通过 cookie `invest_access_token` 或 Authorization header 传递
- **refresh_token**：有效期 14 天，支持 refresh family 防重放攻击
- **CSRF**：写操作校验 `x-csrf-token` header
- **登录安全**：密码最少 10 位，需含大小写字母和数字；连续失败 5 次锁定 15 分钟

### 5.2 角色权限矩阵

| 权限 | admin | ops | ops-readonly | support | client-readonly |
|---|:---:|:---:|:---:|:---:|:---:|
| auth.manage | * | | | | |
| audit.read | * | * | | | |
| accounts.read | * | * | * | * | |
| accounts.write | * | | | | |
| clients.read | * | * | * | * | |
| clients.write | * | | | | |
| customer.read | * | * | * | * | * |
| dashboard.read | * | * | * | * | |
| fees.read | * | * | * | | |
| fees.write | * | * | | | |
| import.read | * | * | * | | |
| import.write | * | * | | | |
| nav.read | * | * | * | * | * |
| nav.write | * | * | | | |
| price.read | * | * | * | | |
| price.write | * | * | | | |
| rates.read | * | * | * | | |
| rates.write | * | * | | | |
| reports.read | * | * | * | * | * |
| scheduler.read | * | * | * | | |
| scheduler.run | * | * | | | |
| shares.read | * | * | * | * | * |
| shares.write | * | * | | | |

**说明**：admin 独有 auth.manage（用户管理）和 accounts.write / clients.write（基金/账户/客户创建）。份额流水/台账的编辑和删除需要 admin 角色（除权限外还有显式角色检查）。

### 5.3 默认用户

| 用户名 | 角色 | 密码 | 说明 |
|---|---|---|---|
| admin | admin | Admin12345 | 管理员 |
| ops | ops | Ops1234567 | 运营 |
| ops.viewer | ops-readonly | Viewer12345 | 运营只读 |
| client1 | client-readonly | Client12345 | 客户示例 |

---

## 6. 前端页面

### 6.1 页面清单

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | 概览 | 系统首页 |
| `/login` | 登录 | 用户认证 |
| `/auth/complete` | 登录跳转 | cookie 稳定后跳转目标页 |
| `/dashboard` | 仪表盘 | 关键指标汇总 |
| `/funds` | 基金管理 | 基金 CRUD，状态/净值/份额概览 |
| `/nav` | 净值台账 | NAV 记录列表，计算（支持强制重算） |
| `/shares` | 份额流水 | 申购/赎回/种子资本记录，admin 可编辑/删除 |
| `/register` | 份额台账 | 权威份额变动登记，admin 可编辑/删除 |
| `/accounts` | 账户管理 | 券商账户 CRUD |
| `/accounts/[id]` | 账户详情 | 4 个 Tab：持仓、交易、导入、现金 |
| `/import` | 数据导入 | CSV 上传、预览、确认 |
| `/cash` | 现金管理 | 现金头寸 CRUD |
| `/clients` | 客户管理 | 客户 CRUD |
| `/customers/[id]` | 客户视图 | 客户份额、NAV、资本账户聚合展示 |
| `/reports` | 报表 | 期间报表概览 + CSV 导出 |
| `/initialize` | 基金初始化 | 7 步向导创建并激活基金 |
| `/settings` | 系统设置 | 汇率/价格管理、定时任务、用户管理 |

### 6.2 导航结构

前端导航栏分为 5 个分组，各导航项根据用户权限自动显示/隐藏：

| 分组 | 包含页面 |
|---|---|
| 概览 (Overview) | 首页, 仪表盘 |
| 基金管理 (Fund) | 基金, 净值, 份额流水, 份额台账 |
| 账户与交易 (Account) | 账户, 导入, 现金 |
| 客户 (Client) | 客户管理, 客户视图 |
| 运营 (Ops) | 报表, 基金初始化, 系统设置 |

### 6.3 前端架构模式

- **SSR 数据加载**：每个页面通过 `getServerSideProps` 在服务端获取数据，cookie 自动透传
- **AuthProvider**：React Context 提供 `useAuth()` hook，管理用户状态和权限检查
- **i18n**：`useI18n()` hook 提供 `t()` 翻译函数，locale 存储在 `invest_locale` cookie
- **UI 体系**：统一的 `colors`、`styles` 常量，`FormField` 表单组件，`StatusBadge` 等
- **权限控制**：Layout 组件根据 `requiredPermission` 显示权限不足提示；导航项按权限过滤

---

## 7. 基金生命周期

### 7.1 完整流程

```
创建基金 (draft) → 配置参数 → 录入种子资本 → 创建账户 → 导入持仓 → 录入现金 → 计算 NAV → 激活基金 (active)
```

### 7.2 初始化向导（/initialize）

| 步骤 | 操作 | 说明 |
|---|---|---|
| 1 | 选择/创建基金 | 选择已有 draft 基金或新建 |
| 2 | 配置基金参数 | 类型、货币、费率、申购周期等 |
| 3 | 录入种子资本 | 选择客户（可选）、金额、日期；NAV=1.0 |
| 4 | 账户设置指引 | 引导用户去账户页面创建券商账户 |
| 5 | 现金头寸指引 | 引导用户录入初始现金余额 |
| 6 | 净值计算指引 | 引导用户导入持仓并计算首次 NAV |
| 7 | 激活基金 | 将基金状态从 draft 切换为 active |

### 7.3 NAV 计算逻辑

`backend/app/services/nav_engine.py` 中的 `calc_nav()` 函数：

1. 查询基金下所有账户的持仓（按 nav_date）
2. 对每个持仓，优先使用 AssetPrice 定价，若无则使用持仓 average_cost 兜底
3. 非 USD 资产通过 ExchangeRate 折算
4. 按 asset_code + currency 聚合生成 AssetSnapshot
5. 查询同日现金头寸（CashPosition），按汇率折算为 USD
6. **total_assets_usd = 持仓总值 + 现金总值**
7. **nav_per_share = total_assets_usd / total_shares**
8. 支持 `force=True` 强制删除旧记录后重算

### 7.4 份额管理

- **申购 (subscribe)**：基于当日最新 NAV 计算 shares = amount / nav_per_share
- **赎回 (redeem)**：基于当日最新 NAV 计算赎回份额
- **种子资本 (seed)**：初始 NAV = 1.0，shares = amount（或自定义）
- 每笔操作同时写入 ShareTransaction + ShareRegister + 更新 ClientCapitalAccount

---

## 8. 数据导入

### 8.1 支持平台

| 平台 | source 参数 | 解析器 |
|---|---|---|
| Interactive Brokers | `ib` / `interactive_brokers` | `ib_parser.py` |
| Kraken | `kraken` | `kraken_parser.py` |
| Charles Schwab | `schwab` / `charles_schwab` | `schwab_parser.py` |
| Moomoo / Futu | `moomoo` / `futu` | `moomoo_parser.py` |
| 通用 CSV | 其他值 | 直接解析 |

### 8.2 导入流程

```
上传 CSV ──▶ 预处理器（平台特定格式转换） ──▶ 通用 CSV 解析器 ──▶ 预览
  │                                                                    │
  │         confirm_batch()                                            │
  └──── parsed 状态 ──▶ 生成 Transaction 记录 + 生成/更新 Position 快照 ──▶ confirmed
```

**预处理器架构**：每个平台解析器实现 `preprocess(raw: bytes) -> bytes`，将平台特定格式转换为通用 CSV 格式。

**通用 CSV 格式要求**（必填列）：
- `trade_date` / `asset_code` / `quantity` / `price` / `currency` / `tx_type`
- 支持多种列名别名（如 symbol→asset_code, date→trade_date）

**持仓构建**：导入确认时，按交易记录计算加权平均成本，生成 Position 快照。

---

## 9. 部署

### 9.1 快速启动

```bash
cd invest
./start-local.sh        # 启动 Docker Compose
./smoke-test.sh         # 运行冒烟测试
```

### 9.2 Docker Compose 配置

文件：`docker-compose.local.yml`

| 服务 | 镜像 | 端口 |
|---|---|---|
| db | postgres:16 | 5433:5432 |
| backend | ./backend (Dockerfile) | 8000:8000 |
| frontend | ./frontend (Dockerfile) | 3000:3000 |

数据卷：`invest_pgdata`（PostgreSQL 数据持久化）

### 9.3 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| DATABASE_URL | postgresql+psycopg2://fund_user:fund_pass@db:5432/fund_system | 数据库连接 |
| AUTH_MODE | token | 认证模式 (token/hybrid/dev) |
| AUTH_ALLOW_DEV_FALLBACK | false | 是否允许开发模式降级 |
| AUTH_SECRET_KEY | change-me-invest-dev-secret | JWT 签名密钥（生产环境必须更换） |
| AUTH_TOKEN_TTL_HOURS | 12 | access_token 有效时间 |
| AUTH_REFRESH_TOKEN_TTL_DAYS | 14 | refresh_token 有效时间 |
| AUTH_LOCKOUT_THRESHOLD | 5 | 登录失败锁定阈值 |
| SCHEDULER_ENABLED | false | 是否启用定时任务 |
| SCHEDULER_FX_PAIRS | HKD:USD,SGD:USD,CNY:USD | 自动获取的汇率对 |
| NEXT_PUBLIC_API | http://127.0.0.1:8000 | 前端客户端 API 地址 |
| INTERNAL_API_BASE | http://backend:8000 | 前端 SSR 内部 API 地址 |

### 9.4 数据库初始化

后端启动时自动执行：
1. Alembic 迁移 (`alembic upgrade head`)
2. Bootstrap 用户创建（根据 `AUTH_BOOTSTRAP_USERS_JSON` 配置）

---

## 10. 国际化

- **支持语言**：英文 (en) + 中文 (zh)
- **存储**：用户语言偏好存储在 `invest_locale` cookie
- **实现**：`frontend/lib/i18n.tsx` 提供 `useI18n()` hook，返回 `{ locale, setLocale, t }` 方法
- **使用**：所有用户可见文本通过 `t('key')` 获取翻译
- **覆盖范围**：导航、表单标签、按钮、状态提示、错误信息等全部国际化
