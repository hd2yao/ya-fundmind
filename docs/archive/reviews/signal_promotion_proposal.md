# Signal Promotion Proposal

> 当前没有直接修改主模型；本文件只用于人工审批和后续 PR 评估。

- 是否建议进入主模型：no

## 可以继续实验

- 无

## 需要更多数据

- `tiantian:*:return:*:total_return`: status=needs_data, direction=positive, min_points=20, missing_tests=main score/risk regression, missing/stale/degraded gates. observed_count=0; eligible_rate=None; stability_grade=no_history; data_quality_gate=blocked; config_sensitivity_grade=stable; missing stability history
- `tiantian:*:drawdown:*:max_drawdown`: status=needs_data, direction=negative, min_points=20, missing_tests=main score/risk regression, missing/stale/degraded gates. observed_count=0; eligible_rate=None; stability_grade=no_history; data_quality_gate=blocked; config_sensitivity_grade=stable; missing stability history
- `tiantian:*:volatility:*:volatility`: status=needs_data, direction=negative, min_points=20, missing_tests=main score/risk regression, missing/stale/degraded gates. observed_count=0; eligible_rate=None; stability_grade=no_history; data_quality_gate=blocked; config_sensitivity_grade=stable; missing stability history

## 应拒绝或阻塞

- `akshare:*:display_only:*`: status=rejected, direction=neutral, min_points=0, missing_tests=main score/risk regression, missing/stale/degraded gates. observed_count=4; eligible_rate=0.0; stability_grade=no_history; data_quality_gate=blocked; config_sensitivity_grade=stable; display-only signals cannot enter scoring/risk

## 人工审批清单

- 确认方向假设和阈值候选。
- 确认样本数量、质量等级和 stale cache 处理。
- 确认 warning/degraded/unstable annualized return 不进入主模型。
- 为任何主模型接入单独开 PR 并补主 score / 主 risk 回归测试。
