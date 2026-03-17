# Fund Management System 部署与验收说明

- **项目名称：** Fund Management System
- **当前适用阶段：** Internal Test Ready / 工程化可验收版本
- **仓库：** https://github.com/aaddnet/invest
- **分支：** main
- **更新时间：** 2026-03-17

---

## 1. 说明

本文档用于说明当前版本的：

- 本地部署方式
- Docker 联调方式
- 验收测试方式
- 认证方式
- 常见问题与排查建议

当前版本已支持：

- 数据导入
- NAV 计算
- Share 申购赎回
- Fee 计算
- 客户只读视图
- Reports
- Scheduler
- Audit
- 轻量正式认证（session token）

---

## 2. 环境要求

建议环境：

- macOS / Linux
- Docker Desktop 或可用 Docker daemon
- Docker Compose v2
- Node.js 18+
- Python 3.9+

如果只走 Docker 联调，宿主机不必预装 Python / Node 的全部依赖，但建议保留以便单独调试。

---

## 3. 推荐启动方式：Docker 本地联调

这是当前最推荐的方式。

## 3.1 一键启动

在仓库根目录执行：

```bash
./start-local.sh
```

该脚本会基于当前工程化版本启动：

- PostgreSQL
- FastAPI backend
- Next.js frontend

## 3.2 使用 Docker Compose 直接启动

也可以手动执行：

```bash
docker compose -f docker-compose.local.yml up -d --build
```

## 3.3 默认服务地址

- Frontend: `http://127.0.0.1:3000`
- Backend: `http://127.0.0.1:8000`
- PostgreSQL: `127.0.0.1:5433`

说明：

- 数据库端口使用 **5433**，用于避开宿主机常见的 `5432` 冲突。

---

## 4. 手动启动方式（非 Docker）

适合单独调试 backend 或 frontend。

## 4.1 启动数据库

优先建议仍使用 Docker 只起数据库：

```bash
docker compose -f docker-compose.local.yml up -d db
```

## 4.2 启动后端

进入 backend 目录：

```bash
cd backend
```

激活虚拟环境并启动：

```bash
. .venv312/bin/activate
export DATABASE_URL='postgresql+psycopg2://fund_user:fund_pass@127.0.0.1:5433/fund_system'
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

说明：

- 当前版本启动时会自动执行数据库 migration：
  - `alembic upgrade head`

## 4.3 启动前端

进入 frontend 目录：

```bash
cd frontend
npm install
npm run dev
```

如果需要指定 API 地址：

```bash
export NEXT_PUBLIC_API='http://127.0.0.1:8000'
npm run dev
```

---

## 5. 认证方式

当前版本已支持轻量正式认证。

## 5.1 登录

接口：

```http
POST /auth/login
```

示例：

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

登录成功后会返回 session token。

## 5.2 获取当前用户信息

```bash
curl http://127.0.0.1:8000/auth/me \
  -H 'Authorization: Bearer <TOKEN>'
```

## 5.3 登出

```bash
curl -X POST http://127.0.0.1:8000/auth/logout \
  -H 'Authorization: Bearer <TOKEN>'
```

## 5.4 当前角色

当前支持角色：

- `admin`
- `ops`
- `client-readonly`

说明：

- `client-readonly` 会被限制在自身客户视图范围内。
- 当前是轻量 session auth，不是完整企业级 IAM。

---

## 6. 核心验收步骤

推荐使用 smoke test 做一轮完整验证。

## 6.1 一键 Smoke Test

仓库根目录执行：

```bash
./smoke-test.sh
```

当前 smoke test 会覆盖：

- health
- auth
- import
- nav
- share
- fee
- scheduler
- audit
- customer readonly boundary
- frontend 可访问性

## 6.2 手工验收建议顺序

如果你要人工走一遍，建议顺序如下：

### 第一步：检查服务健康

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
curl -I http://127.0.0.1:3000
```

预期：

- `/health` 返回 `{"status":"ok"}`
- `/health/db` 返回 `{"db":"ok"}`
- 前端返回 `200 OK`

### 第二步：登录

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

记录返回的 token。

### 第三步：验证 import 流程

- 上传 CSV
- 查看 batch detail
- confirm import
- 检查 transaction / position 是否可查询

### 第四步：验证 NAV 流程

- 调用 `/nav/calc`
- 查询 `/nav`
- 确认生成 fund-scoped NAV 记录

### 第五步：验证 share 流程

- 调用 `/share/subscribe`
- 调用 `/share/redeem`
- 查看 `/share/history`
- 查看 `/share/balances`
- 验证超额赎回返回 `400`

### 第六步：验证 fee 流程

- 调用 `/fee/calc`
- 查看 `/fee`

### 第七步：验证 scheduler / audit

- 手动触发 weekly FX job
- 查看 `/scheduler/jobs`
- 查看 `/audit`

### 第八步：验证客户只读边界

- 使用 `client-readonly` 角色登录或上下文
- 验证其无法读取其他客户数据

---

## 7. 数据库 migration

当前版本已经接入 Alembic。

## 7.1 手动执行 migration

```bash
cd backend
. .venv312/bin/activate
alembic upgrade head
```

## 7.2 查看当前版本

```bash
alembic current
```

## 7.3 迁移文件位置

```text
backend/alembic/versions/
```

说明：

- 当前版本已有初始迁移文件。
- 后续新增字段/表结构时，应优先走 migration，而不是继续依赖启动时兼容补列。

---

## 8. 测试说明

## 8.1 后端测试

```bash
cd backend
. .venv312/bin/activate
pytest -q
```

当前应能看到关键 API / parser 测试通过。

## 8.2 前端检查

```bash
cd frontend
npm install
npx tsc --noEmit
```

如果需要启动前端：

```bash
npm run dev
```

---

## 9. 常见问题排查

## 9.1 Docker daemon 未启动

现象：

- `docker compose` 无法连接
- `start-local.sh` 启动失败

处理：

- 确认 Docker Desktop 已启动
- 确认本机 Docker daemon 正常运行

## 9.2 5432 端口冲突

现象：

- PostgreSQL 无法启动

处理：

- 当前默认已改用 `5433`
- 如果仍冲突，检查本机已有数据库进程

## 9.3 前端连不上后端

检查：

- backend 是否运行在 `127.0.0.1:8000`
- `NEXT_PUBLIC_API` 是否配置正确

## 9.4 登录失败

检查：

- 用户是否已存在
- token 是否正确放在 `Authorization: Bearer <TOKEN>`
- session 是否已 logout/revoke

## 9.5 migration 异常

检查：

- `DATABASE_URL` 是否正确
- 当前数据库是否已初始化
- Alembic 版本表是否异常

---

## 10. 当前版本边界说明

当前版本已经具备：

- 工程化可验收能力
- 本地 Docker 联调能力
- session token auth
- migration
- 核心 smoke test

但仍不是完整生产级版本，当前仍缺：

- refresh token
- 密码策略 / lockout
- 完整前端登录态 UI
- 更细粒度权限模型
- 更完整 E2E 测试
- 生产监控与告警

---

## 11. 建议使用方式

如果你现在要做内部验收，建议直接按下面顺序：

1. `./start-local.sh`
2. `./smoke-test.sh`
3. 手工打开前端验证页面
4. 登录并检查 auth / customer boundary
5. 做一轮 import / nav / share / fee 人工回归

如果你要继续进入下一阶段，建议优先做：

- 前端登录态 UI 闭环
- 更完整 migration 管理
- E2E 自动化
- 部署与监控
