# V1 Todo

## 规则

V1 Todo 用来防止主线被零散优化打断。

- P0 blocking: 可以打断当前任务，必须先处理。
- P1 current milestone: 在当前 Milestone 内完成，不跨 Milestone 拖延。
- P2 later polish: 不打断主线，V1 完成后或 Milestone 空档统一优化。

任何 Todo 升级或降级都需要写清楚原因。默认不因为“看起来不错”把 P2 提升到 P0。

## P0 Blocking

当前无已知 P0。

2026-07-03 V1 post-release acceptance 结论：无 P0。

判定标准：

- daily ops 无法运行。
- contract validation 系统性失败。
- scheduler 会删除 outputs/logs/runs/dashboard。
- 数据源失败导致默认 demo/fixture 路径不可用。
- 输出出现买卖建议、收益承诺或交易指令。
- 主评分/主风险被非授权任务修改。

## P1 Current Milestone

当前 Milestone: V1 Released。

- V1 主线已收口。
- 新增能力进入新的路线图或 V2 ideas。
- P0 只保留运行中断、测试失败、数据契约破坏、误输出交易建议等生产级阻塞。

2026-07-03 V1 post-release acceptance 结论：无 P1。

## P2 Later Polish

这些事项不打断 M1-M6 主线。

### 2026-07-03 V1 Post-release Acceptance Observations

- Long-horizon history still has `insufficient_history`: 当前 `runs_processed=5`，主模型升级门槛为 20 个有效 run。该问题只影响主评分/主风险升级判断，不影响 daily、dashboard、Web Console 或现有报告使用。
- Portfolio Analysis 当前为 `warning`: 3 个持仓观察项缺少可用当前估值，代码为 `510300`、`000834`、`110022`。现有页面和 JSON 可用，但组合估值字段后续需要补全。
- Fund Detail coverage 仍需积累：`detail_count=3`、`missing_count=3`、`warning_count=4`。不阻塞 V1 使用，后续可继续增强数据源覆盖率。
- News Evidence 当前使用本地 evidence 底座：`evidence_count=3`、`low_confidence_count=1`。真实新闻/公告扩展属于后续能力，不阻塞 V1。
- Market Intelligence 当前数据质量为 `warning`: `insufficient_sample_themes:2`。继续 daily 运行可以改善主题样本稳定性。
- Scheduler status 文案可优化：`status_launchd_scheduler.sh` 会展示当天日志路径，即使当天 21:30 尚未触发 daily。实际最近成功 daily 为 2026-07-02 21:30，launchd daily 上次退出码为 0。
- Weekly scheduler 已安装并加载，但 launchd 还未到下一次周六 10:00 自动触发窗口；下次 scheduler 调整时建议与 daily 一样固定使用项目 `.venv` Python 路径。

### 2026-07-13 v1.0.3 Ops Fix

- Weekly scheduler 于首次自动触发时因 `PYTHON_BIN=python` 在 launchd 精简 PATH 下不可解析而退出 `127`。
- `v1.0.3` 将安装器默认解释器固定为项目 `.venv/bin/python`（存在时），并在 plist 中写入绝对路径。
- 修复发布后需要重新安装 weekly，并以 `launchctl` 触发和退出码 `0` 作为验收证据。

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
- M2 Historical Backfill 历史回填层：完成 `historical-backfill` CLI、`run_type=historical_backfill` 标记、market snapshots 回填、NAV summary 回填、market trend/fund detail 回填读取和 live/backfill 隔离测试。
- M3 Portfolio Analysis 组合分析层：完成独立 `portfolio-analysis` CLI、`portfolio_report.json/md`、主题/类型暴露、集中度/重叠观察风险、dashboard `portfolio.html`、ops-status/latest_summary portfolio 摘要。
- M4 News / Announcement Evidence 新闻公告证据层：完成独立 `collect-news-evidence` CLI、fixture 新闻证据源、去重、时间戳对齐、source quality / low confidence 标记、`news_evidence_report.json/md`、dashboard `news.html` 和 daily ops 集成。
- M5 Web Console v1：完成本地 `web-console` CLI、Streamlit console、ops status/latest summary、Market/Funds/Portfolio/News/Review/Reports 入口、dashboard refresh、daily ops trigger 和 manual review state 更新能力。
- M6 V1 Release 收口：完成正式 README 使用手册、V1 release report、版本切换到 `v1.0.0`、验证命令和发布边界说明。

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
