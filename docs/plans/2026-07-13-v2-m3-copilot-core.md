# V2 M3 Research Copilot Core Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 提供受约束的 `research-ask` 自然语言入口、确定性研究计划、结构化 ResearchAnswer、无 LLM 中文 renderer 和脱敏 audit，发布 `v1.3.0`。

**Architecture:** Intent Router 只识别有限研究 topic 和交易型 blocked intent；Planner 只调用 M1 Query 与 M2 Evidence；ResearchAnswer 冻结结构化事实；renderer 只把答案渲染为文本；audit 记录脱敏摘要和 hash。Optional renderer 只能返回文本，不能改变结构化 answer。

**Tech Stack:** Python dataclasses、Protocol、regex、hashlib、JSON/JSONL、argparse、pytest。

---

## Intent Taxonomy

- `market`：市场、板块、主题、热点。
- `fund`：基金、ETF，并提取 6 位代码；指定单基金问题缺 code 时返回 data gap。
- `portfolio`：组合、持仓、暴露、集中度。
- `news`：新闻、公告、消息、证据。
- `history`：历史、变化、上期、趋势对比。
- `quality`：数据质量、来源、fallback、stale、置信度。
- `blocked_transaction`：买入、卖出、加仓、减仓、仓位建议、收益承诺、下单、交易、券商。
- `unsupported`：其余问题。

交易型词优先于研究词，防止“根据市场分析告诉我买什么”绕过 guardrail。

## Task 1：Intent / Guardrails

1. 新建 `tests/test_research_guardrails.py`，覆盖 6 类 topic、fund code、unsupported、交易词优先级和 prompt-injection 文本。
2. 确认 RED。
3. 新建 `fund_agent/research_copilot.py`，实现 `ResearchIntent` 和 deterministic classifier。
4. 确认 GREEN。
5. Commit: `feat: add research intent guardrails`。

## Task 2：Planner / ResearchAnswer

1. 新建 `tests/test_research_copilot.py`，覆盖 6 类问题、partial/unavailable、fund code gap、blocked/unsupported。
2. 确认 RED。
3. 在 `models.py` 新增 `ResearchPlan` 和 `ResearchAnswer`。
4. 实现 planner：Query -> Evidence -> Answer；finding/evidence 原样复制，不生成新数值。
5. 确认 GREEN。
6. Commit: `feat: add deterministic research copilot`。

## Task 3：Renderer / Audit

1. 新建 renderer 和 audit 测试，覆盖 deterministic Markdown、optional renderer protocol、失败回退、secret redaction 和 append-only JSONL。
2. 确认 RED。
3. 新建 `fund_agent/copilot_renderer.py` 和 `fund_agent/audit.py`。
4. renderer 只接收 ResearchAnswer 的深复制 payload并返回文本；不接具体 LLM provider。
5. audit 记录 question hash、脱敏 preview、intent/status、counts 和 output path。
6. 确认 GREEN。
7. Commit: `feat: add copilot renderer and audit`。

## Task 4：CLI / Contract / Release

1. 新建 `tests/test_research_ask_cli.py` 和 ResearchAnswer contract 测试。
2. 确认 RED。
3. 新增 `research-ask --question --output-dir --output --markdown-output`。
4. 默认写 `outputs/copilot/research_answer.json/md` 和 `outputs/audit/research_queries.jsonl`。
5. 新增 `research-answer-v1` contract、validator 和文档。
6. 真实 outputs 运行六类问题、blocked 和 unsupported；验证 answer 中的 finding/evidence 与 M2 一致。
7. 全量 pytest、compileall、V1/M1/M2 contract、demo/daily/Web 回归。
8. 更新版本 `1.3.0`、README、CHANGELOG、roadmap、tasks、backlog、release report。
9. PR/CI/merge，main 验收后 tag `v1.3.0`。

## Gate

- `AC-010` 至 `AC-014` 满足。
- 无 LLM、无网络、无 secret 可完成六类问题。
- 每个非拒绝 finding 均来自 Evidence Bundle。
- blocked/unsupported 不访问 provider、不生成交易指令。
- optional renderer 不能改变 JSON answer。
- V1/M1/M2 不回归，不修改评分、风险或交易边界。
