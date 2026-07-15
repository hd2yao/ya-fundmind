# Documentation Index

当前文档同时维护稳定运行的 V1 基线和已进入 `v2.0.0-rc.1` 的 V2 Research Copilot。M1-M6 RC 技术门已完成；Final 只等待严格的 post-RC 真实运行门，不再使用无限 Phase 追加方式。

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

## V2 RC Entry Points

- `releases/v2.0.0-rc.1-release-report.md`：RC 验收证据和 Final 剩余门禁。
- `migrations/v1-to-v2.md`：安装、兼容和回滚。
- `ops/v2-troubleshooting.md`：查询、Evidence、MCP、Web、provider、scheduler 和 readiness 排障。
- `contracts/v2-release-readiness-v1.md`：机器可读发布门契约。
