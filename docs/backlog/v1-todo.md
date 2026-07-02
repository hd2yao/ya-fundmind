# V1 Todo

## 规则

V1 Todo 用来防止主线被零散优化打断。

- P0 blocking: 可以打断当前任务，必须先处理。
- P1 current milestone: 在当前 Milestone 内完成，不跨 Milestone 拖延。
- P2 later polish: 不打断主线，V1 完成后或 Milestone 空档统一优化。

任何 Todo 升级或降级都需要写清楚原因。默认不因为“看起来不错”把 P2 提升到 P0。

## P0 Blocking

当前无已知 P0。

判定标准：

- daily ops 无法运行。
- contract validation 系统性失败。
- scheduler 会删除 outputs/logs/runs/dashboard。
- 数据源失败导致默认 demo/fixture 路径不可用。
- 输出出现买卖建议、收益承诺或交易指令。
- 主评分/主风险被非授权任务修改。

## P1 Current Milestone

当前 Milestone: M2 Historical Backfill 历史回填层。

- 设计并实现 `historical-backfill` CLI。
- 明确 `run_type=historical_backfill`，并与 live daily run 严格区分。
- 支持 fund NAV 历史回填。
- 支持 market snapshot 历史回填。
- 防止用今天 live 数据伪造过去日期。
- 让 market trend / fund detail 能读取 backfill 数据，并明确展示 backfill 标记。
- M2 验收前补齐必要测试。

## P2 Later Polish

这些事项不打断 M1-M6 主线。

- README 截图或本地 dashboard 使用截图。
- Dashboard 视觉细节统一。
- Markdown 文档措辞统一。
- 输出目录清理脚本。
- 更细的 provider warning 文案。
- 更完整的 changelog 分组。
- Dashboard 表格排序和前端筛选增强。
- 更多 fixture 数据样本。
- 更细的 cache retention 策略。
- 文档中增加 FAQ。

## Completed Milestones

- M1 Fund Detail 通用化收尾：完成 `unknown_reason`、`data_coverage`、`peer_comparison`、dashboard coverage/peer 展示、ops-status/latest_summary coverage 摘要。

## 不进入 V1 Todo 的事项

以下事项属于 V2 ideas，不进入 V1 Todo，也不阻塞 V1：

- Agent 问答。
- MCP。
- LangGraph。
- LLM 自动解释。
- 投资博主 Skill。
- 自动推荐。
- 自动交易。
- 券商接入。
- SaaS。
- 移动端。
- 小程序。
