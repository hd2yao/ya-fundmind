# V3 M1 组合未知估值收口

## 目标

落实 V3 `AC-002`：持仓缺少当前估值时，将未知保持为 `null`，而不是写入 `0` 并继续推导出虚假的总值、收益率、权重、集中度或暴露结论。

## 行为契约

- 全部持仓缺少估值时：`valuation_status=unavailable`，`total_value`、组合收益率、持仓权重和集中度为 `null`。
- 部分持仓缺少估值时：`valuation_status=partial`；保留 `valued_position_count`、`unvalued_position_count` 和 `valued_total_value` 作为覆盖信息，但 `total_value` 和组合收益率仍为 `null`。
- 全部持仓估值可用时：保持现有总值、权重、暴露和集中度语义。
- 旧主评分、主风险、daily/weekly、provider 与用户配置不变。

## 验收

1. 缺估值不会生成 `current_value=0`、`-100%`、`0%` 权重或伪造暴露。
2. 组合页的 TypeScript contract 接受 `null`，并继续显示“当前估值不可用”。
3. `pytest`、`compileall`、Web typecheck/test/build 通过。

## 回滚

本批只变更组合分析输出和前端类型声明；回滚单个 Git commit 即可，不涉及 SQLite、缓存、调度或配置文件。
