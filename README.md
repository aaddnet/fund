# Invest / Fund Management System

当前仓库已从 `Internal Test Ready` 继续推进到更工程化的本地可联调状态，重点补强了：

- 更正式的 token/session 鉴权
- Alembic 数据库迁移
- Docker 本地一键联调
- 关键 API / parser 回归测试
- P2 报表增强：分组汇总、趋势视图、导出
- P2 CI 基础：GitHub Actions + 本地统一检查脚本
- P2 监控基础：liveness/readiness/metrics hooks

## Quick start

### 1. 一键启动本地联调

```bash
./start-local.sh
```

默认会启动：

- PostgreSQL
- FastAPI backend
- Next.js frontend

端口：

- Frontend: <http://127.0.0.1:3000>
- Backend: <http://127.0.0.1:8000>

### 2. 登录获取 token

系统会自动 bootstrap 本地测试用户（全新数据库初始化时）：

- `admin / Admin12345`
- `ops / Ops1234567`
- `client1 / Client12345`
- `ops.viewer / Viewer12345`

> 注意：如果你使用的是旧数据库卷，历史 seed 用户密码可能不会被自动覆盖，需以当前库里实际账号状态为准。

示例：

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -F 'username=ops' \
  -F 'password=ops123'
```

然后用返回的 `access_token` 调用接口：

```bash
curl http://127.0.0.1:8000/auth/me \
  -H "Authorization: Bearer <token>"
```

## Reports (P2)

报表页已支持：

- 月 / 季 / 年筛选
- 基金 / 客户 / 份额交易类型筛选
- 按基金、客户、交易类型聚合的份额流汇总
- 按日期的净流入趋势条形图
- 按基金的最新 NAV 摘要
- 交易资产分布摘要
- 前端导出 JSON / CSV

核心接口：

```bash
curl "http://127.0.0.1:8000/reports/overview?period_type=quarter&period_value=2026-Q2&tx_type=subscribe" \
  -H "Authorization: Bearer <token>"
```

## Monitoring hooks (P2)

轻量级 observability / alert-ready hooks：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/metrics/json
```

说明：

- `/health/live`：进程存活探针
- `/health/ready`：数据库 ready 探针
- `/metrics`：Prometheus 文本格式，便于后续接 Grafana / Alertmanager
- `/metrics/json`：便于本地排查的 JSON 快照
- 所有请求会记录简单 in-memory 路由计数、5xx 数、平均耗时

## Auth modes

通过环境变量控制：

- `AUTH_MODE=token`：只允许 Bearer token
- `AUTH_MODE=hybrid`：优先 Bearer token，允许保留 dev fallback
- `AUTH_MODE=dev`：旧的开发头模式

推荐本地联调使用：

```env
AUTH_MODE=hybrid
AUTH_ALLOW_DEV_FALLBACK=true
```

更接近正式测试可改为：

```env
AUTH_MODE=token
AUTH_ALLOW_DEV_FALLBACK=false
```

## Database migrations

后端启动时会自动执行：

```bash
alembic upgrade head
```

也可手动执行：

```bash
cd backend
DATABASE_URL='postgresql+psycopg2://fund_user:fund_pass@127.0.0.1:5432/fund_system' alembic upgrade head
```

## Smoke test

本地栈启动后执行：

```bash
./smoke-test.sh
```

会验证：

- health / db health
- auth login / auth me
- import upload / confirm
- nav calc
- share subscribe / redeem
- fee calc
- scheduler / audit
- client readonly scope boundary
- frontend 首页可访问

## Tests / CI

本地统一检查：

```bash
bash scripts/ci-check.sh
```

分别执行：

```bash
cd backend && pytest
cd frontend && npm run build
```

仓库已包含 `.github/workflows/ci.yml`，可直接作为后续 PR / push 自动检查骨架。

## Docker compose

如果你想直接操作 Docker：

```bash
docker compose -f docker-compose.local.yml up --build
```

## Notes

- 当前 auth 已经比纯 dev header 正式很多，但仍是适合现阶段 scaffold 的轻量实现，不是完整企业级 IAM。
- 这段代码可以优化，后续可以继续补真正的告警投递、持久化 metrics、前端更正式的图表组件和更细粒度的导出模板。
