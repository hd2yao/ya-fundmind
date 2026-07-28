# Documentation Index

当前文档同时维护稳定运行的 V1 基线、`v2.0.0` Research Copilot、`v2.1.0` Local Product Web、`v2.2.0` Fund Data Terminal 和 `v2.3.0` Fund Research Desk。各版本均使用有限 Milestone 和明确发布门，不再使用无限 Phase 追加方式。

## Active Delivery Docs

| Directory | Use |
| --- | --- |
| `architecture/` | V1 稳定架构和 V2 目标架构。 |
| `roadmap/` | V1 完成记录和 V2 M1-M6 交付门槛。 |
| `backlog/` | V1 维护项、V2 当前 Todo 和剩余 ideas。 |
| `plans/` | 当前大版本设计和实现主计划；完成后可归档。 |
| `contracts/` | 机器可读输出契约和 schema versioning。 |
| `ops/` | Scheduler automation 和 readiness semantics。 |
| `migrations/` | V1 到 V2 的非破坏性升级与回滚说明。 |
| `releases/` | 版本发布报告和验证证据。 |
| `../specs/` | V2 验收标准、任务映射和执行契约。 |

## Archive

| Directory | Use |
| --- | --- |
| `archive/legacy-plans/` | Historical Phase 1-12 and V1 milestone implementation plans. |
| `archive/research/` | Initial open-source study and gap analysis. |
| `archive/reviews/` | Historical review/proposal outputs. |

Archived files are not part of the day-to-day operating manual. They are retained for traceability and should not block future work.

## What Can Be Deleted Locally

These files are runtime or OS noise and should not be committed:

- `.DS_Store`
- `__pycache__/`
- `.pytest_cache/`
- `outputs/`
- `data/cache/`
- local `.venv/`

## What Should Not Be Deleted

- `README.md`
- `PROJECT_STRUCTURE.md`
- `docs/architecture/`
- `docs/roadmap/`
- `docs/backlog/`
- `docs/contracts/`
- `docs/ops/`
- `docs/releases/`
- `docs/plans/` 中仍在执行的计划
- `specs/`

## Rule For Future Docs

新 active docs 应回答当前架构、契约、运行或交付问题。已完成且只用于追溯的历史实现计划和研究记录应移入 `docs/archive/`。

## V2 Release Entry Points

- `releases/v2.0.0-rc.1-release-report.md`：RC 验收证据和 Final 剩余门禁。
- `releases/v2.0.0-release-report.md`：Final 真实运行、验证和发布证据。
- `releases/v2.1.0-release-report.md`：本地 Product Web、全市场基金搜索和 launchd 发布证据。
- `releases/v2.2.0-m1-acceptance.md`：任意已索引基金的按需历史净值验收。
- `releases/v2.2.0-m2-acceptance.md`：主要指数历史行情、缓存和 API 验收。
- `releases/v2.2.0-m3-acceptance.md`：行业板块目录、历史走势、缓存、API 和三视口验收记录。
- `releases/v2.2.0-m4-acceptance.md`：数据终端信息架构、全局搜索和四视口验收。
- `releases/v2.2.0-release-report.md`：Fund Data Terminal 最终发布、已知外部限制和回滚证据。
- `plans/2026-07-27-v2.3-market-freshness-research-workbench.md`：市场新鲜度与研究工作台实现记录。
- `plans/2026-07-28-v2.3-to-v2.6-product-delivery.md`：基金详情、组合工作台和证据浏览器的后续有限版本计划。
- `releases/v2.3.0-release-report.md`：Fund Research Desk 发布、验证证据和回滚说明。
- `migrations/v1-to-v2.md`：安装、兼容和回滚。
- `ops/v2-troubleshooting.md`：查询、Evidence、MCP、Web、provider、scheduler 和 readiness 排障。
- `contracts/v2-release-readiness-v1.md`：机器可读发布门契约。
