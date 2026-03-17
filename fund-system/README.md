# Fund Management System (legacy scaffold docs)

新的本地联调入口已提升到仓库根目录：

- `../docker-compose.local.yml`
- `../start-local.sh`
- `../smoke-test.sh`
- `../README.md`

## 推荐使用方式

从仓库根目录执行：

```bash
cd ..
./start-local.sh
```

或：

```bash
docker compose -f docker-compose.local.yml up --build
```

## 保留本目录的原因

本目录仍保留早期 scaffold 资料，方便追溯，但后续以根目录的联调脚本和文档为准。
