# V3 M1 跨模块回归门禁计划

## 目标

为 V3 M1 添加一个离线、可重复的 fixture 运维回归门禁。它证明 Product API/前端信息架构改动没有改变既有 daily/weekly 研究闭环、新闻证据、组合观察、contract 或主评分/主风险边界。

## 执行契约

- 测试只使用 `fixture` provider 和 `tmp_path` 输出目录；不访问真实网络、不读取或写入正式 `outputs`。
- 分别运行 `scripts/run_daily_ops.sh` 和 `scripts/run_weekly_ops.sh`，覆盖 scheduler 实际调用的脚本入口。
- 断言 daily run 成功、run bundle 完整、news evidence 有结构化记录、weekly summary 只做研究汇总、dashboard 可生成，并再次运行严格 contract validation。
- 对 daily summary、news evidence、portfolio report、ops status 断言 `main_score_changed=false`、`main_risk_changed=false`、`not_production_model=true`；对 weekly summary 断言 `no_trading_simulation=true`。
- 对 `configs/watchlist.yaml` 和 `configs/portfolio.yaml` 做前后 digest 比较，确保任务不会改写用户配置。

## 验收标准

1. 默认 pytest 不依赖真实网络，并能通过该 end-to-end fixture test。
2. daily/weekly script 都返回 0，`ops_status` 记录成功 run 和 dashboard。
3. `fund_agent_report.json`、snapshot、trace 三类 contract 都通过校验。
4. 新闻 fixture 仍是证据产物而非交易或推荐输入；报告免责声明仍然可见。
5. 不修改主评分、主风险、provider 默认值、watchlist、portfolio 或 scheduler。

## 非目标

- 不修复或掩盖 fixture 数据质量为 `degraded` 的事实；它与“主模型未被修改”是不同问题。
- 不接入真实新闻、真实交易、券商、自动推荐或主模型升级。
- 不改变正式产品 Web 的普通用户视图。

## 实施结果

- 新增 `tests/test_v3_m1_regression_gate.py`，在默认无网络 pytest 中实际运行 fixture daily/weekly shell script。
- 验证 run bundle、新闻证据、组合观察、dashboard、ops status 与 report/snapshot/trace contract；长期样本不足只保留为研究门禁，不阻塞本测试。
- 验证 daily/news/portfolio/ops 均声明主评分和主风险未变，weekly 保持无交易模拟，并对 watchlist/portfolio 配置做前后 digest 校验。
