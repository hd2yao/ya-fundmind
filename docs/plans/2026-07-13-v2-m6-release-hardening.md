# V2 M6 Release Hardening Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用可重复的兼容、安全、性能、端到端和真实运行证据发布 `v2.0.0-rc.1`，清零 P0/P1 后发布 YA FundMind OS `v2.0.0`。

**Architecture:** 不新增投研业务能力，不改变主评分、主风险或 daily provider。新增只读 release-readiness 边界来审计既有 run bundle，并用独立测试矩阵验证 V1 artifact -> Query -> Evidence -> Copilot -> CLI/MCP/Web 的单向兼容；RC 与 Final 使用两个独立 PR/tag 门。

**Tech Stack:** Python 3.10+ 标准库、pytest、现有 JSON contracts、Streamlit optional、官方 MCP Python SDK optional、GitHub Actions、launchd 本地验收。

---

## 冻结边界

- 不修改 `fund_agent/scoring.py`、主 `RiskIssue` 生成逻辑、watchlist、portfolio、provider 默认或 scheduler 安装配置。
- 不新增推荐、仓位、交易、券商、收益承诺、SaaS、多用户或公网能力。
- 默认 pytest/CI 不访问真实网络；AKShare/Tiantian/MCP/Streamlit 继续 optional。
- 历史 run 只读，不复制、改写或伪造日期。RC 观察必须来自不同日期的真实成功 run。
- Release readiness 只判定 V2 发布质量，不改变 `long_horizon` 或主模型 promotion gate。
- pre-RC 历史 run 只能用于 `historical_compat`；Final 必须使用带版本、commit、dirty 与 trigger 溯源的 `post_rc` run。

## Task 1：计划和基线

**Files:**

- Create: `docs/plans/2026-07-13-v2-m6-release-hardening.md`

**Steps:**

1. 记录 `v1.5.0`、PR #28、merge commit `9bbfa16` 和 `352 passed, 1 skipped` 基线。
2. 审计 scheduler、最近 run、现有 security/compatibility tests 和真实 outputs 性能。
3. 提交计划：`docs: detail v2 m6 release hardening`。

## Task 2：Release Readiness / RC Run Observation

**Files:**

- Create: `fund_agent/release_readiness.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/v2-release-readiness-v1.md`
- Create: `tests/test_release_readiness.py`
- Modify: `tests/test_contract_validation.py`
- Modify: `tests/test_cli.py` 或 Create: `tests/test_release_readiness_cli.py`

**Step 1: 写 RED 测试**

- 三个不同 ISO 日期 run，daily summary、run metadata、daily step、validate_contract step 和必需 JSON artifact 全部成功时 `status=pass`。
- warning quality 可观察；degraded/critical、fallback、critical provider warning、live rows 为 0、缺文件、失败 step 或边界字段变化必须排除并给 reason。
- fixture/synthetic run 不得计入真实 RC observation。
- 少于 `minimum_valid_runs` 返回 blocker 和 CLI exit 1；达到要求 exit 0。
- JSON 必须包含 schema/generated_at/generator/release_target/boundaries/performance/contract_summary/run_observations/blockers/warnings。
- `validate-contract --release-readiness` 和 `validate-contract --output-dir` 通过。

**Step 2: 确认 RED**

Run: `python -m pytest -q tests/test_release_readiness.py tests/test_release_readiness_cli.py tests/test_contract_validation.py`

Expected: FAIL，release readiness service/CLI/contract 尚不存在。

**Step 3: 最小实现**

- 只读取 `output_dir/runs/YYYY-MM-DD`。
- 必需 artifact：`daily_research_summary.json`、`run_metadata.json`、`fund_agent_report.json`、`snapshot.json`、`provider_trace.json`。
- run 必须有 `status=success`、daily/validate_contract step success、`missing_artifacts=[]`、`not_production_model=true`、`main_score_changed=false`、`main_risk_changed=false`。
- provider 必须非 fixture/synthetic、`live_row_count>0`、`fallback_used=false`、无 critical warning。
- 输出 `outputs/release/v2_release_readiness.json`，不改其他 artifact。
- `run_metadata.json` 新增 `provenance`；`post_rc` 模式精确校验 RC app version、merge commit、clean worktree 和 scheduler trigger。

**Step 4: GREEN 和 focused regression**

Run: `python -m pytest -q tests/test_release_readiness.py tests/test_release_readiness_cli.py tests/test_contract_validation.py`

**Step 5: 提交**

Commit: `feat: add v2 release readiness gate`

## Task 3：V1/V2 Compatibility + Security Matrix

**Files:**

- Create: `tests/test_v2_compatibility_matrix.py`
- Create: `tests/test_v2_security_matrix.py`
- Modify production files only if a RED test exposes a real bug.

**Compatibility RED cases:**

- report/snapshot/trace/market/fund/portfolio/news 旧 schema 缺少新增可选字段时 Query 不崩溃。
- 未知字段被忽略；Markdown/HTML 不被 Catalog/Query 当事实来源。
- legacy context -> evidence -> answer 保留 warning/data gap，不生成无 citation 肯定 finding。
- V2 query/ask 不覆盖 V1 report/snapshot/trace。

**Security RED cases:**

- symlink、absolute path、`..`、未注册 artifact 被阻止。
- prompt injection 不能改变 topic allowlist、只读边界或 guardrail 优先级。
- question/audit/MCP error 中 API key、token、password、Bearer、Cookie 和私有路径不落盘。
- ask/query/MCP/Web 不修改 watchlist、portfolio、评分、风险或 scheduler 文件。

**Verification:**

Run: `python -m pytest -q tests/test_v2_compatibility_matrix.py tests/test_v2_security_matrix.py tests/test_artifact_loader.py tests/test_mcp_adapter.py tests/test_mcp_gateway.py tests/test_research_guardrails.py`

**Commit:** `test: harden v2 compatibility and security matrix`

## Task 4：Performance Budget + End-to-End Matrix

**Files:**

- Create: `tests/test_v2_performance.py`
- Create: `tests/test_v2_end_to_end.py`
- Create: `docs/ops/v2-performance-budget.md`
- Modify production files only if measured budgets fail.

**Budgets:**

- 典型本地 outputs（约 100 个 catalog artifacts）：Catalog p95 <= 750ms、market query <= 1200ms、deterministic answer <= 2000ms。
- CI synthetic budget 使用更保守上限 5 秒，避免共享 runner 抖动；同时断言 compact output 不复制完整 market records。
- 当前真实基线：Catalog 153-172ms、market query 262-282ms、market answer 379-385ms。

**E2E cases:**

- fixture 生成 V1 report/snapshot/trace/market 后，market/fund/portfolio/news/history/quality 六类 query/answer 均有预期 status。
- 每个肯定 finding 有 citation；拒绝请求无 finding/交易动作。
- 全部 V1/V2 contract 通过；主报告 hash 在 Query/Evidence/Copilot 后不变。
- Web state、MCP adapter 和 CLI 读取同一公共 service 输出。

**Commit:** `test: add v2 performance and end to end gates`

## Task 5：RC 文档、版本和发布

**Files:**

- Create: `docs/migrations/v1-to-v2.md`
- Create: `docs/ops/v2-troubleshooting.md`
- Create: `docs/releases/v2.0.0-rc.1-release-report.md`
- Modify: `README.md`
- Modify: `PROJECT_STRUCTURE.md`
- Modify: `docs/README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture/v2-system-architecture.md`
- Modify: `docs/roadmap/v2-delivery-roadmap.md`
- Modify: `docs/backlog/v2-todo.md`
- Modify: `specs/v2-research-copilot/tasks.md`
- Modify: `pyproject.toml` to PEP 440 `2.0.0rc1`

**Steps:**

1. 对照 `AC-001` 至 `AC-025` 建立证据表。
2. 写 V1 -> V2 无迁移/可选依赖/回滚说明和本地故障排查。
3. 运行 fresh full verification、fixture daily/weekly、contracts、MCP/Skill、Web/Playwright。
4. PR/CI/merge，在合并后的 main 重跑后 tag/push `v2.0.0-rc.1`。

**Commit:** `docs: prepare v2.0.0 rc1 release`

## Task 6：RC 真实观察与 Ops 验收

**No source edits unless a P0/P1 is found.**

**Commands:**

```bash
python -m fund_agent.cli release-readiness --output-dir outputs --minimum-valid-runs 3 --release-target v2.0.0 --observation-mode post_rc --required-app-version 2.0.0rc1 --required-git-commit "$(git rev-parse HEAD)" --json-output outputs/release/v2_release_readiness.json
python -m fund_agent.cli validate-contract --output-dir outputs
bash scripts/status_launchd_scheduler.sh
python -m fund_agent.cli web-console --output-dir outputs --dry-run
```

**Acceptance:**

- 2026-07-10、2026-07-11、2026-07-12 只作为 pre-RC compatibility 样本；真实 Final observation 必须来自 RC merge 后三个不同日期的新 run，并由 `post_rc` readiness 逐项验证，不得手写为 pass。
- daily/weekly installed+loaded，最近 exit code 0；21:30 daily/weekly 配置不改。
- July 11 warning 允许保留为已观察质量事件，但不能有 fallback/critical/degraded。
- optional MCP 在隔离 venv 安装官方稳定 1.x 并跑 integration；未安装不得报成功。
- AKShare 使用既有真实 run 证据；只有网络和时间允许时再跑可选 smoke，不覆盖正式历史。
- P0/P1 为 0 才进入 Final；否则发布 RC patch。

## Task 7：Final `v2.0.0`

**Files:**

- Create: `docs/releases/v2.0.0-release-report.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/roadmap/v2-delivery-roadmap.md`
- Modify: `docs/backlog/v2-todo.md`
- Modify: `specs/v2-research-copilot/tasks.md`
- Modify: `pyproject.toml` to `2.0.0`

**Steps:**

1. 从 RC merge 后的 `main` 创建新 `codex/` worktree。
2. 记录 RC readiness、3 个真实 run、scheduler、MCP/Web 和 P0/P1=0 证据。
3. fresh 运行 pytest、compileall、contracts、六类 query/answer、fixture daily/weekly、Web 3 viewport 和 scheduler status。
4. focused release diff，提交、PR、CI、merge。
5. 合并后 final smoke，tag/push `v2.0.0`。
6. 做 post-release ops check；不自动开始 V3。

## Stop / Rewind Conditions

- 发现主评分、主风险、交易、券商、配置或 scheduler 被 V2 写入：立即停止，P0。
- 真实 run 不足 3 个或无法证明来源：RC 保持，不发布 Final。
- contract/CI/Web/MCP 任一 P0/P1 未清零：先发 RC patch，不绕过。
- 需要 secret、付费服务、删除 outputs 或改变 V1 schema 语义：回到 spec 评审。
