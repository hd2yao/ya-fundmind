# V2 M2 Evidence & Citation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 M1 Research Context 转换为有原始 artifact/JSON Pointer 引用、质量门、冲突提示和缺口说明的 Evidence Bundle，发布 `v1.2.0`。

**Architecture:** Evidence builder 读取已验证 Research Context，按 topic 的 finding spec 白名单加载原 artifact，并为存在的明确字段生成 EvidenceRef 和 ResearchFinding。Quality Gate 根据 descriptor、provider health/warnings 和数据状态降级；Conflict Gate 只比较相同 claim key 的跨来源不同值。

**Tech Stack:** Python dataclasses、hashlib、JSON Pointer、pytest、现有 ArtifactLoader/ResearchContext contract。

---

## Finding Spec

- `market`：total funds/ETFs、top/hot themes、rising/falling/persistent/new themes、market history sufficiency、warnings。
- `fund`：code/name/type/theme/returns/data coverage/peer comparison/missing fields/warnings。
- `portfolio`：holding count/value、theme/type exposure、concentration、observation issues/warnings。
- `news`：evidence count、low-confidence count、source/theme/fund summaries、items/warnings。
- `history`：latest snapshot delta、timeline count、latest as_of。
- `quality`：report grade/provider warnings、ops readiness、daily grade/status、long-horizon blockers。

不存在的字段只进入 `data_gaps`，不得生成肯定 finding。

## Quality Gate

- `blocked`：critical provider warning、无可定位证据、artifact 被 loader blocked。
- `degraded`：stale cache、artifact quality degraded、来源冲突。
- `warning`：fallback、普通 provider warning、样本不足、legacy schema warning。
- `normal`：没有上述问题。

Bundle 取所有 finding/evidence 的最差等级。`degraded`/`blocked` 或冲突时 `review_required=true`。

## Task 1：Evidence 模型和 JSON Pointer

1. 新建 `tests/test_research_evidence.py`，覆盖 EvidenceRef id、RFC 6901 escape/resolve、有效/无效 pointer、无证据不生成 finding。
2. 运行确认 RED。
3. 在 `fund_agent/models.py` 新增 `EvidenceRef`、`ResearchFinding`、`EvidenceBundle`。
4. 新建 `fund_agent/research_evidence.py`，实现 pointer 和 citation builder。
5. 运行确认 GREEN。
6. Commit: `feat: add research evidence references`。

## Task 2：Quality / Conflict Gate

1. 新建 `tests/test_research_quality_gate.py`，覆盖 normal、warning、fallback、stale、degraded、critical、样本不足和跨来源冲突。
2. 运行确认 RED。
3. 实现 `QualityDecision`、bundle grade 聚合和 conflict detector。
4. 运行确认 GREEN。
5. Commit: `feat: add research evidence quality gate`。

## Task 3：Topic Evidence Builder

1. 新增 market/fund/portfolio/news/history/quality builder 测试。
2. 运行确认 RED。
3. 实现 finding spec、artifact selection、原 payload pointer 和 data gaps。
4. 确认 finding 均有 EvidenceRef，未发现字段不造值。
5. 运行确认 GREEN。
6. Commit: `feat: build topic evidence bundles`。

## Task 4：CLI / Contract / Release

1. 新建 `tests/test_research_evidence_cli.py` 和 contract 测试，覆盖 success/partial/invalid context/contract/exit code。
2. 运行确认 RED。
3. 新增 `build-research-evidence --context --output-dir --output`。
4. 新增 `evidence-bundle-v1` contract、validator 和文档。
5. 真实 outputs 生成 context + evidence，验证 pointer 能回到原字段。
6. 全量 pytest、compileall、V1 contract、demo/daily/Web 回归。
7. 更新版本 `1.2.0`、README、CHANGELOG、roadmap、tasks、backlog、release report。
8. PR/CI/merge，main 验收后 tag `v1.2.0`。

## Gate

- `AC-006` 至 `AC-009` 满足。
- 关键 finding 至少有一个有效 EvidenceRef。
- 无证据不生成肯定 finding。
- stale/fallback/degraded/critical 和冲突安全降级。
- V1/M1 contract 和 CLI 不回归。
- 不修改主评分、主风险、配置、scheduler 或交易边界。
