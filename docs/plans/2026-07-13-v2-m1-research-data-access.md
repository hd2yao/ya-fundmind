# V2 M1 Research Data Access Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立白名单 Artifact Catalog、contract-aware loader、紧凑 ResearchContext 查询和 `research-query` CLI，发布 `v1.1.0`。

**Architecture:** Catalog 只扫描预定义 V1 JSON 路径并生成 descriptor；loader 负责路径隔离、JSON 解析和兼容 warning；query service 按 topic 提取紧凑上下文，不复制全市场 records；CLI 只处理参数和输出。

**Tech Stack:** Python dataclasses、pathlib、hashlib、json、argparse、pytest。

---

## 数据选择规则

- `market`：读取 market intelligence/trend；保留 totals、themes、top/hot/rising/falling/persistent/new、quality 和 warnings，排除 `records`、`classifications`。
- `fund`：优先读取独立 `fund_detail_{code}.json`；否则从 watchlist detail 的 `fund_details` 选择 code。没有 code 时返回 watchlist 摘要。
- `portfolio`：返回 portfolio report 小型结构。
- `news`：返回 news evidence 小型结构。
- `history`：返回 snapshot descriptor timeline 和最新 snapshot 的 compact delta，不复制所有历史 payload。
- `quality`：返回 report/provider health、ops、daily、long-horizon 的质量和 readiness 摘要。

## Task 1：ArtifactDescriptor / Catalog

1. 新建 `tests/test_artifact_catalog.py`，覆盖白名单发现、稳定 id/hash、metadata、顺序、忽略未登记 JSON。
2. 运行测试确认因模块不存在而 RED。
3. 在 `fund_agent/models.py` 新增 `ArtifactDescriptor`。
4. 新建 `fund_agent/artifacts.py`，实现 registry、scan 和 find。
5. 运行 catalog 测试确认 GREEN。
6. Commit: `feat: add research artifact catalog`。

## Task 2：Contract-aware loader

1. 新建 `tests/test_artifact_loader.py`，覆盖 missing、invalid JSON、non-object、missing schema、path traversal 和 unknown optional field。
2. 运行测试确认 RED。
3. 在 `fund_agent/artifacts.py` 实现 `ArtifactLoadResult` 和 `ArtifactLoader`。
4. 运行 loader + catalog 测试确认 GREEN。
5. Commit: `feat: add safe artifact loader`。

## Task 3：ResearchContext / Query Service

1. 新建 `tests/test_research_query.py`，覆盖六个 topic、compact market、fund code、partial 和 no Markdown parsing。
2. 运行测试确认 RED。
3. 在 `fund_agent/models.py` 新增 `ResearchContext`。
4. 新建 `fund_agent/research_query.py`，实现 selectors 和 service。
5. 运行 query + artifact 测试确认 GREEN。
6. Commit: `feat: add unified research query service`。

## Task 4：CLI / Contract

1. 新建 `tests/test_research_query_cli.py`，覆盖参数、默认 output、stdout、partial exit 和 invalid code。
2. 更新 contract tests，先确认 RED。
3. 修改 `fund_agent/cli.py` 增加 `research-query`。
4. 修改 `fund_agent/contract.py` 增加 research context validator 和单文件类型识别。
5. 新增 `docs/contracts/research-context-v1.md`。
6. 运行相关测试、全量 pytest、compileall、fixture daily、contract validation 和真实 outputs query。
7. 更新 README、CHANGELOG、roadmap、tasks、backlog、PROJECT_STRUCTURE 和 release report，版本改为 `1.1.0`。
8. PR/CI/merge；main 再验收后 tag `v1.1.0`。

## Gate

- `AC-001` 至 `AC-005` 满足。
- V1 daily/weekly/Web/contract 不回归。
- 默认测试无网络。
- 不修改评分、风险、provider 默认、watchlist、portfolio 或交易边界。
