# Fund Management System V1 交付报告

- **项目名称：** Fund Management System
- **当前状态：** Internal Test Ready
- **仓库：** https://github.com/aaddnet/invest
- **分支：** main
- **交付时间：** 2026-03-17

---

## 1. 项目目标

根据 `fund_system_v2.docx`，V1 目标是交付一个本地可运行的小型基金管理系统，覆盖以下能力：

- 多账户资产汇总
- 多币种折算
- 月度 NAV 计算
- 份额申购赎回
- 年度业绩报酬计提
- 客户只读视图
- 手动上传对账单并确认入库
- 月 / 季 / 年数据查看
- 每周汇率拉取

V1 不包含：

- AI 摘要 / AI 解析
- 自然语言问答
- GCP 混合部署
- Celery + Redis
- 复杂外部审计报告格式

---

## 2. 当前交付结论

当前版本已经从原型推进到：

## **Internal Test Ready**

说明：

- 核心业务链路已基本建立
- 主要页面和 API 已从占位实现转为真实数据驱动
- 已具备内部演示、联调、试运行和验收基础
- 尚未达到生产上线标准

---

## 3. 本轮交付完成内容

### 3.1 数据导入流程

已完成：

- CSV 上传
- 导入预览
- 导入确认
- 导入批次状态管理：`uploaded` / `parsed` / `confirmed` / `failed`
- confirm 后写入 `transaction`、`position`

接口：

- `POST /import/upload`
- `GET /import`
- `GET /import/{id}`
- `POST /import/{id}/confirm`

前端页面：

- `frontend/pages/import.tsx`

结论：最小可用闭环已具备。

### 3.2 NAV 计算能力

已完成：

- 按 `fund_id + nav_date` 计算 NAV
- 仅聚合属于目标基金的账户和持仓
- 支持 FX 快照折算
- 支持 richer asset snapshot
- NAV 结果可锁定

接口：

- `POST /nav/calc`
- `GET /nav`

结论：已具备 V1 核算主干能力。

### 3.3 份额申购赎回与账本

已完成：

- 申购
- 赎回
- 份额历史查询
- 当前份额余额查询
- 自动同步 `fund.total_shares`
- 超额赎回保护
- 历史记录筛选

接口：

- `POST /share/subscribe`
- `POST /share/redeem`
- `GET /share/history`
- `GET /share/balances`

结论：核心份额账本能力已形成。

### 3.4 Fee / 业绩报酬记录

已完成：

- fee 计算
- richer fee 字段记录：
  - `nav_start`
  - `nav_end_before_fee`
  - `annual_return_pct`
  - `excess_return_pct`
  - `fee_base_usd`
  - `fee_amount_usd`
  - `nav_after_fee`
  - `applied_date`

接口：

- `POST /fee/calc`
- `GET /fee`

结论：已具备基础业绩报酬记录能力。

### 3.5 真实查询接口

已完成：

- `fund`
- `client`
- `account`
- `position`
- `transaction`

接口示例：

- `GET /fund`
- `GET /fund/{id}`
- `GET /client`
- `GET /client/{id}`
- `GET /account`
- `GET /account/{id}`
- `GET /position`
- `GET /position/{id}`
- `GET /transaction`
- `GET /transaction/{id}`

结论：已从原型 API 升级为可用查询 API。

### 3.6 运营端页面

已完成数据驱动页面：

- Dashboard
- Accounts
- Clients
- Import
- NAV
- Shares
- Reports

特点：

- 已接真实后端数据
- 支持基础过滤与查看
- 减少本地 state 草稿式占位交互

结论：运营端已具备内部使用雏形。

### 3.7 客户只读视图

已完成：

- 最小客户视图
- 可查看当前 share balance
- 可查看 share transaction history
- 可查看相关 fund NAV history

接口 / 页面：

- `GET /customer/{client_id}`
- `frontend/pages/customers/[clientId].tsx`

结论：V1 客户只读能力已落地最小版本。

### 3.8 报表与查询

已完成：

- overview 报表接口
- 支持 `month / quarter / year`
- 支持 `fund_id / client_id` 过滤
- 前端 reports 页面

接口 / 页面：

- `GET /reports/overview`
- `frontend/pages/reports.tsx`

结论：已具备基础报表查询能力。

### 3.9 Scheduler

已完成：

- 集成 APScheduler
- weekly FX job
- 手动触发 job
- job 执行记录查询

接口：

- `POST /scheduler/jobs/fx-weekly/run`
- `GET /scheduler/jobs`

结论：已满足 V1 每周汇率拉取的最小实现。

### 3.10 Auth / Role Boundary

已完成：

- 最小 dev auth
- 角色：`admin` / `ops` / `client-readonly`
- 客户只读流边界限制

结论：已具备内部测试所需的最小权限边界。

### 3.11 Audit / Logging

已完成：

- `audit_log`
- `/audit` 只读接口
- 关键动作审计：
  - import upload
  - import confirm
  - nav calc
  - fee calc
  - share subscribe
  - share redeem
  - scheduler 手动触发

结论：已具备内部验收级审计基础。

### 3.12 测试补强

已完成：

- API 级轻量测试
- 关键失败用例测试
- smoke test 扩展

结论：测试基础已建立，但仍需继续加强。

---

## 4. 关键提交记录

- `f18a069` — `feat: implement real csv import workflow`
- `ba188f8` — `Implement fund-scoped NAV and real query APIs`
- `a38dcb7` — `feat: tighten share ledger and enrich fee records`
- `f62b52f` — `feat: add week 3 ops customer and reports views`
- `9fbece9` — `feat: add week 4 scheduler auth and audit support`

---

## 5. 当前完成度评估

### 已基本完成

- 多账户资产汇总
- 多币种折算（基础版）
- 月度 NAV 计算
- 份额申购赎回记录
- 客户只读视图（最小版）
- 手动上传对账单 + 确认入库
- 月 / 季 / 年数据查看（基础版）
- 汇率自动拉取（基础 scheduler 版）

### 已部分完成

- 业绩报酬计提
  - 已有实现，但仍偏最小可用逻辑，后续可继续增强

### 未纳入本期

- 生产级认证
- 云部署
- AI 解析 / AI 摘要
- 高级报表
- 更强审计与风控

---

## 6. 当前版本定位

建议当前版本对内统一描述为：

## **V1 Internal Test Ready**

也可以更口语化地描述为：

- 可内部试运行
- 可验证核心账务流程
- 不建议直接生产上线

---

## 7. 当前风险与不足

### 7.1 认证机制仍是开发级

当前 auth 为最小 dev auth，不是正式用户认证。

### 7.2 数据库 migration 仍不完整

当前存在兼容补列逻辑，正式环境应使用 migration 管理。

### 7.3 Docker / 本地一键联调环境未彻底验证

代码链路已测通，但本机 Docker daemon 未启动，标准联调仍需环境侧确认。

### 7.4 测试覆盖仍不够全面

仍缺：

- 更完整 API tests
- parser tests
- E2E tests
- 权限边界更系统化测试

### 7.5 生产化能力不足

例如：

- 正式登录鉴权
- 部署监控
- 告警
- 更严格约束和数据校验

---

## 8. 建议下一阶段工作

### P0

- 打通正式认证体系
- 做数据库 migration
- 完整打通 Docker / 本地联调环境
- 补关键 API / parser 测试

### P1

- 强化 fee / NAV 业务规则精度
- 增强报表与导出
- 完善客户视图交互
- 补更多审计查询能力

### P2

- 做部署、监控、告警
- 评估后续 GCP / 云端演进
- 再考虑 V2 能力

---

## 9. 最终结论

当前版本已经完成了 **V1 核心业务骨架与内部测试能力建设**，项目已从“演示原型”推进到“可内部试运行”的阶段。

阶段标签建议：

- 原先：`Alpha Prototype`
- 当前：`Internal Test Ready`
- 距离生产：仍需进一步工程化补强
