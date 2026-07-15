# V1 到 V2 迁移指南

## 结论

YA FundMind OS V2 是建立在 V1 JSON artifact 之上的只读 Research Copilot。V1 的 daily/weekly、配置、cache、report、snapshot、provider trace、dashboard 和主评分/主风险不需要数据迁移，也不需要删除后重建。

V2 新增的是独立输出与可选接口：

- `outputs/research_queries/research_context.json`
- `outputs/evidence/research_evidence.json`
- `outputs/copilot/research_answer.json` 与 `.md`
- `outputs/audit/research_queries.jsonl` 与 `mcp_calls.jsonl`
- `outputs/release/v2_release_readiness.json`

## 升级前检查

```bash
git status --short
git branch --show-current
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli validate-contract --output-dir outputs
```

不要提交 `outputs/`、SQLite cache、日志、`.env` 或本地凭据。用户维护的 `configs/watchlist.yaml` 和 `configs/portfolio.yaml` 不应被版本升级覆盖。

## 安装

基础研究与默认离线测试：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web]"
```

可选能力按需安装：

```bash
python -m pip install -e ".[live]"  # AKShare
python -m pip install -e ".[mcp]"   # 本地只读 MCP
```

默认 CI 和 pytest 不安装 live provider，也会阻止 socket 网络连接。真实 provider smoke 仍是显式手动操作。

## 升级后验证

```bash
python -m fund_agent.cli validate-contract --output-dir outputs
python -m fund_agent.cli research-query --output-dir outputs --topic market
python -m fund_agent.cli build-research-evidence --output-dir outputs
python -m fund_agent.cli research-ask \
  --output-dir outputs \
  --question "今天市场和热门板块有什么变化？"
python -m fund_agent.cli web-console --output-dir outputs --dry-run
```

旧 snapshot 缺少 `schema_version` 时仍可兼容读取并产生 warning；RC/Final 发布门禁使用 strict validation，不接受旧 schema 作为发布证据。

## Scheduler

V2 不修改 daily 21:30 或 weekly 周六 10:00 的计划。scheduler 继续调用仓库内 `scripts/run_daily_ops.sh` / `run_weekly_ops.sh`，因此代码切换到 V2 后会自然使用新版本。

新 daily run 的 `run_metadata.json` 会增加：

```json
{
  "provenance": {
    "app_version": "2.0.0rc1",
    "git_commit": "<main commit>",
    "git_dirty": false,
    "trigger": "daily_ops",
    "python_version": "3.12.x"
  }
}
```

这些字段只用于证明 post-RC 运行来源，不改变研究结果。scheduler 安装状态可用下列命令复核：

```bash
bash scripts/status_launchd_scheduler.sh
```

## 兼容边界

- V2 只从白名单 JSON artifact 构建事实，不解析 Markdown/HTML。
- 未知可选字段会被忽略；缺失字段产生 warning/data gap，不猜值。
- Query、Evidence、Copilot、MCP 不覆盖 V1 report/snapshot/trace。
- MCP、Web、LLM renderer 都是可选层；缺失不影响 daily/weekly。
- 不修改主评分、主风险、provider 默认、watchlist、portfolio 或 scheduler schedule。
- 不自动交易、不接券商、不输出买卖建议、不承诺收益。

## 回滚

V2 新输出与 V1 artifact 解耦。发生问题时可先停止使用 Copilot/MCP/Web，并继续运行 V1 daily/weekly；无需删除任何 outputs。

代码回滚建议从稳定 tag 建立独立分支，不使用破坏性 reset：

```bash
git fetch --tags
git switch -c rollback/v1.5.0 v1.5.0
python -m pip install -e ".[dev,web]"
python -m fund_agent.cli validate-contract --output-dir outputs
```

回滚不会要求删除 V2 新目录；V1 会忽略它不认识的输出。
