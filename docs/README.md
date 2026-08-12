# Documentation Index

当前文档同时维护稳定运行的 V1/V2 基线和正在交付的 V3 Fund Information Platform。稳定产品版本为 `v2.6.0`；V3 M1 已发布 `v3.0.0-alpha.1`，M2 本地候选已通过实现、真实数据和浏览器门禁，远端 PR/CI/push/tag 尚未执行。各大版本使用有限 Milestone 和明确发布门，不使用无限 Phase 追加方式。

## Active Delivery Docs

| Directory | Use |
| --- | --- |
| `architecture/` | V1/V2 稳定架构和 V3 目标架构。 |
| `design/` | 当前产品 UI Design Lock。 |
| `roadmap/` | V1/V2 完成记录和 V3 M1-M6 交付门槛。 |
| `backlog/` | 稳定版本维护项和 V3 当前 Todo。 |
| `reviews/` | 当前版本的证据化产品审计。 |
| `research/` | 当前有效的开源项目与数据源研究。 |
| `plans/` | 当前大版本设计和实现主计划；完成后可归档。 |
| `contracts/` | 机器可读输出契约和 schema versioning。 |
| `ops/` | Scheduler automation 和 readiness semantics。 |
| `migrations/` | V1 到 V2 的非破坏性升级与回滚说明。 |
| `releases/` | 版本发布报告和验证证据。 |
| `../specs/` | V2/V3 验收标准、任务映射和执行契约。 |

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

## V3 Delivery Entry Points

- `reviews/2026-07-28-v2.6-product-reassessment.md`：v2.6 能力、页面和数据真实性审计。
- `research/2026-07-28-fund-platform-open-source-refresh.md`：AKShare 和参考项目模块映射。
- `architecture/v3-fund-information-platform.md`：V3 产品与技术架构。
- `design/v3-fund-information-platform-design-lock.md`：V3 任务、信息、布局和视觉约束。
- `roadmap/v3-delivery-roadmap.md`：V3 M1-M6、版本和发布门。
- `backlog/v3-todo.md`：V3 P0/P1/P2。
- `plans/2026-07-28-v3-fund-information-platform.md`：TDD 实现主计划。
- `releases/v3.0.0-alpha.1-release-report.md`：M1 alpha 发布证据、边界和回滚。
- `reviews/2026-08-12-v3-m2-fund-profile-acceptance.md`：M2 本地数据、代码、浏览器和边界验收。
- `releases/v3.0.0-alpha.2-release-report.md`：M2 alpha.2 候选状态与待完成远端门禁。
- `contracts/fund-profile-v1.md`：M2 基金概况、交易规则和费率资料契约。
- `plans/2026-07-28-v3-m2-fund-profile-data.md`：M2 实现、测试、发布与回滚计划。
- `../specs/v3-fund-information-platform/`：Spec、技术方案、任务和执行契约。

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
- `releases/v2.4.0-release-report.md`：基金独立详情、真实本地历史净值浏览和回滚说明。
- `migrations/v1-to-v2.md`：安装、兼容和回滚。
- `ops/v2-troubleshooting.md`：查询、Evidence、MCP、Web、provider、scheduler 和 readiness 排障。
- `contracts/v2-release-readiness-v1.md`：机器可读发布门契约。
