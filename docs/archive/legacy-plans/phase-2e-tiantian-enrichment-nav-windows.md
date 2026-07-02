# Phase 2E Tiantian Enrichment Stabilization + NAV Windows

## Phase 2E 目标

Phase 2E 增强 Tiantian enrichment 的可用性，但仍不改变 daily 默认 provider，不接入评分模型，不接入风险主逻辑。

本阶段完成：

- `nav_history_summary` 增加窗口参数。
- `enrich-fund` 增加 `--nav-windows`。
- `enrich-fund` 增加显式 `--allow-cache` fallback。
- provider trace 增加 Tiantian cache/window 可选字段。
- 定义未来评分/风险输入契约。

## NAV Windows

支持窗口：

- `1m`
- `3m`
- `6m`
- `1y`
- `all`

默认窗口：

```bash
1m,3m,6m
```

JSON 示例：

```json
{
  "nav_history_summary": {
    "510300": {
      "count": 120,
      "source": "tiantian",
      "windows_requested": ["1m", "3m", "6m"],
      "windows_generated": ["1m", "3m", "6m"],
      "windows": {
        "1m": {
          "count": 20,
          "start_date": "2026-05-23",
          "end_date": "2026-06-23",
          "latest_unit_nav": 5.03,
          "latest_accumulated_nav": 5.03,
          "total_return": 1.2,
          "annualized_return": 14.8,
          "max_drawdown": -2.1,
          "volatility": 0.8,
          "missing_days": 10,
          "source": "tiantian",
          "data_quality_grade": "warning",
          "metadata": {
            "annualized_return_unstable": false
          }
        }
      }
    }
  }
}
```

窗口样本不足时，`data_quality_grade` 会标记为 `warning` 或 `degraded`。短样本年化收益会在 `metadata.annualized_return_unstable` 和 `metadata.annualized_return_note` 中标记。

这些指标仅用于观察，不进入评分和风险主逻辑。

## enrich-fund 使用方式

真实 Tiantian enrichment：

```bash
export TIANTIAN_API_BASE_URL=http://127.0.0.1:3000
python -m fund_agent.cli enrich-fund --provider tiantian --code 510300 --output-dir outputs --nav-windows 1m,3m,6m,1y
```

支持 `all`：

```bash
python -m fund_agent.cli enrich-fund --provider tiantian --code 510300 --output-dir outputs --nav-windows 1m,3m,6m,1y,all
```

参数错误会返回清晰错误，例如：

```bash
Unsupported nav window: bad. Supported windows: 1m, 3m, 6m, 1y, all
```

## allow-cache 行为

显式 cache fallback：

```bash
python -m fund_agent.cli enrich-fund --provider tiantian --code 510300 --output-dir outputs --allow-cache
```

行为：

- live Tiantian client 成功时，优先使用 live 并写入 cache。
- live client 不可用或 live fetch 失败时，只有显式传入 `--allow-cache` 才读取 cache。
- cache 命中时，输出 `fund_details` 和 `nav_history_summary`。
- cache 数据 source 标记为 `cache:tiantian`。
- cache stale 时写入 `stale_cache` warning。
- cache 缺失时返回清晰错误，不伪造成功。

## Tiantian Cache Fallback 限制

Cache fallback 只用于显式 enrichment，不进入 daily 默认流程。

限制：

- 需要同时命中 fund detail 和 nav history。
- stale cache 只允许报告生成和人工复核，不应用作自动交易或收益承诺。
- cache fallback 不代表真实 Tiantian live smoke 成功。

## Provider Trace

Tiantian trace 继续遵守 `provider-trace-v1`，并以可选字段记录：

- `cache_read_count`
- `fallback_used`
- `fallback_reason`
- `fallback_source`
- `warnings`
- `windows_requested`
- `windows_generated`

示例：

```json
{
  "provider": "tiantian",
  "fallback_used": true,
  "fallback_reason": "TiantianFundProvider client is not configured",
  "fallback_source": "cache:tiantian",
  "cache_read_count": 3,
  "cache_write_count": 0,
  "windows_requested": ["1m", "3m", "6m"],
  "windows_generated": ["1m", "3m", "6m"],
  "warnings": [
    {
      "code": "live_fallback",
      "severity": "warning"
    }
  ]
}
```

## 为什么仍不接评分/风险

NAV windows、评级、规模和基金详情字段需要先稳定字段语义、样本门槛、缺失处理和回归测试。Phase 2E 只做数据可用性增强和契约定义，不改变现有评分和风险解释。

未来接入前需遵守：

- `docs/contracts/scoring-risk-input-contract.md`

## 验证命令

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli daily --provider fixture --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli validate-contract --output-dir outputs
```

如果设置了真实 Tiantian 兼容服务：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
python -m fund_agent.cli enrich-fund --provider tiantian --code 510300 --output-dir outputs --nav-windows 1m,3m,6m,1y
```

## Phase 2F 建议

- 增加手动 `smoke-tiantian` CI job。
- 增加 Tiantian cache fallback 的单独诊断命令。
- 定义 NAV windows 的固定交易日窗口，而不是自然日近似。
- 在独立实验分支评估 Tiantian 字段对评分/风险的影响，不直接改主模型。
