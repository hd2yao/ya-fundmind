# V2 本地性能预算

## 适用范围

该预算覆盖 YA FundMind OS v2 的只读链路：Artifact Catalog、Research Query、Evidence Bundle 与 deterministic Research Copilot。它不覆盖 AKShare/Tiantian 网络请求，也不承诺公网服务级别。

## 预算

典型本地目录定义为不超过 100 个已注册 JSON artifact、总量不超过 32 MiB：

| 操作 | 本地目标 | CI 防抖上限 |
|---|---:|---:|
| Catalog scan | 500 ms | 5,000 ms |
| 单主题 Query | 750 ms | 5,000 ms |
| Evidence Bundle | 500 ms | 5,000 ms |
| deterministic Answer | 1,000 ms | 5,000 ms |

`release-readiness` 使用更宽松的发布阻断预算：Catalog 750 ms、Market Query 1,200 ms、Market Answer 2,000 ms。发布机实测结果必须写入 readiness JSON，不能只引用测试阈值。

## 体积约束

- Query 仅读取注册 JSON artifact，不解析 Markdown/HTML。
- Market context 不复制全量 `records`、`classifications`。
- History context 仅输出 timeline 与最新 delta，不复制全部 snapshot payload。
- Finding 必须引用 Evidence ID；没有证据不得生成肯定 finding。

## 回归命令

```bash
python -m pytest -q tests/test_v2_performance.py tests/test_v2_end_to_end.py
python -m fund_agent.cli release-readiness --output-dir outputs --minimum-valid-runs 3
```

共享 CI runner 只使用 5 秒防抖上限；真实发布仍以 readiness 中的本机测量及本文件“本地目标”为准。
