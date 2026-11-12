# dagpilot · 离线批作业 DAG 编排与 SLA 回填窗口台

> 把「依赖只在老员工脑子里」的 24 个离线作业变成一张可校验、可排期、可回填的地铁线路图。

## 真实场景

**客户**：山海数据 · 数仓运维组（5 人）。127 个离线作业按 4 条链路每天 01:00 起跑；
本台覆盖其中与早会报表强相关的 24 个作业。

**现有工作流**：`crontab` + 人工盯。依赖关系散落在老员工脑子与一份两年前的文档里；
早上报表打不开，才顺着日志回溯是哪条上游迟到。

**三个痛点**

1. 依赖不可视、环无人校验：有人加了一条反向边，第二天整条链路静默不跑。
2. 关键路径与 SLA 风险无法预判：只知道「昨晚跑了 5 小时」，不知道卡在哪一段、P90 会不会超。
3. 补数窗口拍脑袋：补多了挤爆集群（同一晚 4 条链路并发），补少了赶不上 SLA。

**上下游**：上游 = 作业历史运行记录（时长/状态）+ 依赖配置 →
本台替代「人工维护依赖 + 经验排期」→ 下游 = 调度器（导出 DAG 排期 CSV）与值班告警。

## 角色与权限

| 角色 | 邮箱 | 主要页面 | 权限点 | 典型动作 |
|---|---|---|---|---|
| `admin` 数仓负责人 | `admin@dagpilot.io` | 全部 | `job:write` `dep:write` `dag:validate` `run:simulate` `sla:write` `backfill:read` `alert:ack` `export:read` `audit:read` | 改作业分位时长、导入依赖、调 SLA 截止与缓冲 |
| `operator` 值班工程师 | `operator@dagpilot.io` | 线路图 / 模拟运行 / 回填窗口 / 值班台 | `dag:validate` `run:simulate` `backfill:read` `alert:ack` `export:read` | 跑模拟、看关键路径、生成补数建议、确认告警 |
| `viewer` 业务方（只读） | `viewer@dagpilot.io` | 值班台 / 线路图只读 | `estimate:read` | 看「几点能出数」，不能跑模拟 / 不能补数 / 不能改依赖 |

密码统一 `Demo@2026`。低权角色调高权接口由服务端返回 **403**（不是前端藏按钮）：
`viewer` 调 `POST /api/simulations`、`POST /api/sla/backfill-suggestion`、`POST /api/dependencies/import` 全部 403；
`operator` 调 `POST /api/jobs`、`PATCH /api/sla/policies/{id}` 也是 403。

## 一天的工作剧本（2026-11-12）

| 时间 | 谁 | 做什么 | 真实对象与数值 |
|---|---|---|---|
| 01:00 | 调度器 | 四条链路发车 | L1/L2/L3 01:00、L4 02:30 |
| 01:34 | 集群 | 并发峰值 | 7 个作业同时运行（扫描线口径） |
| 04:12 | 郑迟（operator） | 打开值班台 | 报表出数线 P50 预计 04:12 出数 |
| 04:15 | 郑迟 | 看 P90 风险 | 报表线 P90 06:48，超 SLA 06:30 共 **18 分钟** |
| 04:20 | 郑迟 | 跑一次模拟运行 | 关键路径 3h12m（P50）= `ads_report_stage → ads_trade_daily → ads_report_join → ads_report_qc → ads_report_export` |
| 04:25 | 郑迟 | 生成回填窗口建议 | latest_start 00:12、窗口 16h12m、可补 **2 天**、集群峰值并发 **7** |
| 04:30 | 郑迟 | 导出排期 CSV 给调度器 | `dagpilot-schedule-report-run*.csv` |
| 08:00 | 沈岸（admin） | 把报表线 SLA 缓冲从 30 提到 35 分钟 | `PATCH /api/sla/policies/1` |
| 09:10 | 沈岸 | 导入依赖（补一条 `ads_store_daily → ads_report_export`） | 先试算校验 0 环，再合并导入 |

## 主要功能（4 个业务模块串成链路）

1. **作业 / 依赖维护**（`/jobs`）：站表（作业清单）、SVG 自绘分层线路图、依赖边列表、导入依赖（试算校验 → 合并）、校验（Kahn 拓扑 + 环检测）。
2. **校验**：返回拓扑序、分层、环路径、P50/P90 链路时长与峰值并发。
3. **运行模拟**（`/simulate`）：按 P50 / P90 两套分位重排整条链路，输出关键路径链、逐作业 ES/EF/LS/LF 与总浮时、时序条、并发带、SLA 判定；结果落库可复现。
4. **回填建议**（`/sla`）：latest_start / 可用窗口 / 可回填天数 / 剩余松弛 / 集群峰值并发 / 逐天补数排期。
5. **导出**：排期 CSV、回填计划 CSV。
6. **值班台**（`/watch`）：由 SLA 快照 + 历史批次派生的等待/告警列表（含确认），链路就绪看板。

## 两个真算算法

### 算法 1 · 拓扑排序与关键路径（`backend/src/services/dag_service.py`）

输入：作业列表（含 `p50_seconds` / `p90_seconds`）+ 依赖边（含 `lag_minutes`）。

```
Kahn 拓扑排序（编码字典序入堆，保证同一张图输出完全一致）
  剩余入度非零点做 DFS → 返回一条真实环路径（首尾同点）
EST(j) = max(EFT(p) + lag(p→j))        前驱为空则 0
EFT(j) = EST(j) + dur(j)               dur 取 P50 或 P90
LFT(j) = min(LST(s) − lag(j→s))        后继为空取链路总时长
LST(j) = LFT(j) − dur(j)
总浮时  = LST − EST；总浮时 = 0 的作业构成关键路径
链路总时长 = max(EFT) = 关键路径各作业时长之和（含 lag）
并发峰值 = 扫描线（同一分钟先处理结束，A 结束 == B 开始不算并发）
```

失败态：有环 → 返回环路径并拒绝出排期；未知作业编码 / 自环 → 422。

**可复现**：报表出数线 P50 关键路径 `34+52+45+33+28 = 192 分钟 = 3h12m`；
P90 关键路径 `62+96+84+61+45 = 348 分钟 = 5h48m`；两次调用结果逐字一致。

### 算法 2 · SLA 回填窗口（`backend/src/services/backfill_service.py`）

```
latest_start = SLA 截止 − P90 链路时长 − 缓冲(默认 30min)
kickoff_delay = 计划起跑 − latest_start            (>0 表示晚点发车)
overrun       = max(0, 计划起跑 + P90 链路 − SLA 截止)
              = max(0, kickoff_delay − 缓冲)       两式恒等，接口同时返回便于对账
window        = 次日 latest_start − as_of
可回填天数     = floor(window ÷ 每日链路时长)，并封顶 7 天
剩余松弛       = window − 天数 × 每日链路时长
集群峰值并发   = 扫描线扫「当晚 4 条链路按 P50 起跑的排期 ∪ 补数排期」
```

失败态：链路有环 / 没有作业 / 没有生效 SLA → 直接抛错，不输出建议。

**可复现**：报表线 → `latest_start = 06:30 − 5h48m − 0:30 = 00:12`；
as_of = 2026-11-12T08:00 → 窗口 16h12m（972 分钟）→ 可补 `floor(972/348) = 2` 天，剩余松弛 276 分钟（4h36m）；
集群峰值并发 7，峰值时刻 01:34。

## 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 前端 http://localhost:18244  ·  后端 http://localhost:19244/api/health
```

5 个服务：`frontend`(Nginx + dist) / `backend`(FastAPI) / `worker`(Celery) / `db`(MySQL 8.0) / `redis`(7)。
全部带 healthcheck；`backend` 与 `worker` 等 `db`/`redis` healthy，`frontend` 等 `backend` healthy。
`SEED_DEMO=true` 时 backend 启动自动跑一次幂等 seed（失败只记日志不阻塞）。

本地开发：

```bash
# 后端
cd backend && pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
# 前端
cd frontend && npm install && npm run dev     # 5173，/api 代理到 19244
```

## 演示账号

| 邮箱 | 角色 | 密码 |
|---|---|---|
| `admin@dagpilot.io` | 数仓负责人 | `Demo@2026` |
| `operator@dagpilot.io` | 值班工程师 | `Demo@2026` |
| `viewer@dagpilot.io` | 业务方（只读） | `Demo@2026` |

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite 5 + React Router 6，SVG 自绘（无图表库） |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic v2 |
| 任务 | Celery 5.4（worker 容器，beat 心跳 + 每 10 分钟 SLA 巡检） |
| 数据库 | MySQL 8.0（utf8mb4，JSON 列存逐作业时序） |
| 缓存 | Redis 7（限流计数器、worker 心跳、告警确认状态） |
| 视觉 | 地铁线路图风 · Rubik + Noto Sans SC · oklch 色板 · 米黄纸底 |

## 目录

```
backend/
  src/{config,constants,models,schemas,services,controllers,routes,middlewares,utils}/
  scripts/{seed_demo.py,demo_config.py,worker_healthcheck.sh}
  migrations/0001_initial.sql
frontend/
  src/{api,stores,types,components/common,components/layout,hooks,pages,router,utils,constants,styles}/
docker-compose.yml  .env.example
```

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | Compose 项目名 / 容器前缀 | `dagpilot` |
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 端口映射 | `18244` / `19244` / `17744` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` | MySQL | 见 `.env.example` |
| `JWT_SECRET` | JWT 签名密钥 | 见 `.env.example` |
| `REDIS_URL` | Celery broker / 限流 / 告警确认 | `redis://redis:6379/0` |
| `SEED_DEMO` | 启动是否自动 seed | `true` |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_WRITE_PER_MINUTE` | 限流额度 | `300` / `60` |
| `APP_TIMEZONE_OFFSET_MINUTES` | 排班业务时区偏移（分钟） | `480`（UTC+8） |

## 共享枚举出现位置

| 枚举 | 后端 | 前端 |
|---|---|---|
| 角色 `Role` | `backend/src/constants/enums.py` · `constants/roles.py` | `frontend/src/constants/roles.ts` · `types/models.ts` |
| 数仓分层 `JobLayer` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` |
| 依赖类型 `DependencyType` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` |
| 运行状态 `RunStatus` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` |
| 分位口径 `RunMode` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` · `types/models.ts` |
| 风险档位 `RiskLevel` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` |

## Docker 说明

- 恰好 5 个服务，顶层 `name: dagpilot`，无 `version:` 字段。
- 命名卷：`db_data`（MySQL 数据）、`redis_data`（AOF）。
- 只用本机已有基础镜像：`python:3.11-slim`、`node:20-alpine`、`nginx:1.27-alpine`、`mysql:8.0`、`redis:7-alpine`。
- 收尾：`docker compose down -v --remove-orphans`。

## 已知简化

见 `batch-20261112/test-artifacts/gb-571/TESTING.md` 的「已知差异」一节（字体在线回退、
补数是排期推演而非真跑 SQL、历史批次为确定性生成等）。

## License

MIT
