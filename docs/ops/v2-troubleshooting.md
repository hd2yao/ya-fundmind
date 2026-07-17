# V2 运行排障

## 快速诊断

```bash
python -m fund_agent.cli validate-contract --output-dir outputs
python -m fund_agent.cli web-console --output-dir outputs --dry-run
YA_FUNDMIND_PROJECT_DIR=/Users/dysania/program/AI/agent/ya-fundmind \
  bash scripts/status_launchd_scheduler.sh
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0-rc.1 \
  --observation-mode historical_compat
```

先看结构化 JSON 和 exit code，不从 Markdown 文案推断系统状态。

## Research Query 显示 unavailable

常见原因：对应主题 artifact 不存在、JSON 损坏或路径不在 registry。

```bash
python -m fund_agent.cli research-query --output-dir outputs --topic quality
python -m fund_agent.cli validate-contract --output-dir outputs
```

重新运行 daily/market/fund/portfolio/news 的既有生成命令；不要手写 JSON 伪造可用状态。

## Evidence 或 Answer 为 partial

`partial` 不是程序崩溃。它通常表示 stale/fallback/provider warning、样本不足、来源冲突或缺字段。检查：

- `outputs/evidence/research_evidence.json.data_gaps`
- `outputs/evidence/research_evidence.json.warnings`
- `outputs/copilot/research_answer.json.review_required`
- `outputs/traces/provider-*.json`

不要把 warning/degraded 数据改写成 normal；先恢复数据源或补足历史样本。

## MCP 未安装

错误应明确提示 optional dependency。安装后先 dry-run：

```bash
python -m pip install -e ".[mcp]"
python -m fund_agent.cli mcp-server --output-dir outputs --dry-run
```

MCP 只提供 `status/catalog/query/ask/evidence`。任意 path、URL、写配置、交易或券商参数都应被拒绝。

## Web Console 启动失败

```bash
python -m pip install -e ".[web]"
python -m fund_agent.cli web-console --output-dir outputs --dry-run
python -m fund_agent.cli web-console --output-dir outputs --port 8501
```

若端口占用，改用其他本地端口。Web Console 不要求公网、登录或 LLM。

## AKShare 超时或 fallback

provider timeout/retry 来自 `configs/providers.yaml`。macOS/Linux 主线程调用使用可中断 deadline；超时后仍按现有规则走 cache fallback，并在 trace/report 中保留原因。

检查：

- endpoint `attempts/success/error/timeout_seconds`
- `fallback_used/fallback_reason/fallback_source`
- `stale` 与 warning severity

不要把 fallback 或 stale cache 当作 live 成功。默认 pytest 不运行真实网络。

## release-readiness 失败

RC 前兼容观察：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0-rc.1 \
  --observation-mode historical_compat
```

Final 必须使用 post-RC 模式：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0 \
  --observation-mode post_rc \
  --required-app-version 2.0.0rc1 \
  --required-git-commit "$(git rev-list -n 1 v2.0.0-rc.1)"
```

Final 发布前若当前 clean `main` 仍精确位于 RC tag，`git rev-parse HEAD` 与上述 tag 命令等价；Final 发布后必须使用 RC tag 复核历史 provenance，不能改成 Final commit。

常见 blocker/reason：

| 代码 | 含义 |
|---|---|
| `insufficient_valid_release_runs` | 少于三个不同日期有效 run。 |
| `contract_validation_failed` | 当前输出未通过 strict contract。 |
| `final_release_requires_post_rc_observation` | 试图用历史兼容观察发布 Final。 |
| `run_provenance_missing` | run 生成于 provenance 接入前。 |
| `run_app_version_mismatch` | run 不是指定 RC 包版本。 |
| `run_git_commit_mismatch` | run 不来自指定 RC main commit。 |
| `run_git_dirty` | 运行时 tracked/untracked 工作树不干净。 |
| `run_trigger_not_scheduler` | run 是直接手动 daily-research，不是 daily ops/scheduler。 |
| `provider_fallback_used` | 该 run 使用 cache fallback。 |
| `critical_provider_warning` | provider 有 critical/error warning。 |

历史 run 只能证明兼容，不能复制日期或修改 metadata 来满足 Final。

## Scheduler

```bash
YA_FUNDMIND_PROJECT_DIR=/Users/dysania/program/AI/agent/ya-fundmind \
  bash scripts/status_launchd_scheduler.sh
launchctl print gui/$(id -u)/com.ya-fundmind.daily
launchctl print gui/$(id -u)/com.ya-fundmind.weekly
```

确认 daily 为 21:30、provider=akshare、Market Intelligence 开启，daily/weekly `last exit code=0`。Final worktree 验证时必须通过 `YA_FUNDMIND_PROJECT_DIR` 指向 launchd 实际使用的主工作区，避免误读隔离 worktree 的空 outputs。`status_launchd_scheduler.sh` 会刷新主工作区 ops status/latest summary，因此不是纯只读命令。

## Audit 与敏感信息

Research/MCP audit 只保存 hash、脱敏预览、计数和状态；路径只保留文件名。若 audit 目标或父目录是 symlink，写入会失败关闭，避免越界追加。

不要把 API key、token、Cookie、密码、`.env` 或绝对私有路径写入问题、artifact、日志或 issue。必须配置 secret 时使用环境变量。
