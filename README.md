# Invest / Fund Management System

当前仓库已从 `Internal Test Ready` 继续推进到更工程化的本地可联调状态，重点补强了：

- 更正式的 token/session 鉴权
- Alembic 数据库迁移
- Docker 本地一键联调
- 关键 API / parser 回归测试

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

系统会自动 bootstrap 本地测试用户：

- `admin / admin123`
- `ops / ops123`
- `client1 / client123`

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

## Tests

```bash
cd backend
pytest
```

## Docker compose

如果你想直接操作 Docker：

```bash
docker compose -f docker-compose.local.yml up --build
```

## Notes

- 当前 auth 已经比纯 dev header 正式很多，但仍是适合现阶段 scaffold 的轻量实现，不是完整企业级 IAM。
- 这段代码可以优化，后续可以继续补 refresh token、password reset、审计告警等。
