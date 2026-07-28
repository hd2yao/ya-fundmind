# V3 M1 行业板块历史可用性验收

日期：2026-07-28

范围：V3 M1 Product Truth & Information Architecture 的行业板块历史展示闭环。
结论：功能修复完成，等待 PR、CI 与 clean `main` 发布门禁；不创建 `alpha.1` tag 之前不视为发布。

## 问题与根因

产品页可搜索并展示真实行业板块当日行情，但部分板块（例如 `BK1607`“医药流通”）没有可连续展示的历史日线。根因不是页面缓存伪造或固定筛选：当前环境中 AKShare 的东方财富行业日线 endpoint 返回无效响应，而行业目录可正常返回。

不能将“医药流通”近似替换为其他医药板块，这会把不同板块的数据呈现为同一标的。

## 处理决定

1. 保持 AKShare 为唯一 Provider，不新增第二 Provider。
2. 先调用原有东方财富行业日线 endpoint；失败或没有有效点时，只允许调用 AKShare 的同名 THS 行业 endpoint。
3. 仅名称完全一致才可写入该 `BK` 的历史缓存；不能精确匹配时，不补造曲线、不写入替代数据。
4. 新增受控命令：

   ```bash
   python -m fund_agent.cli refresh-market-sector-history \
     --provider akshare --symbols BK1042,BK1036 --output-dir outputs
   ```

   它逐项预热指定行业历史，不改 daily/weekly schedule，也不进入主评分或主风险。
5. 普通产品页保留已选板块的当日行情，历史不可用时仅显示“历史日线暂未取得”及通俗说明；内部 endpoint、provider、cache、warning code 和原始异常只进入 trace/运维面。

## 验证证据

### 离线回归

- Python：`542 passed, 1 skipped`。
- `python -m compileall -q fund_agent`：通过。
- Web：`14` 个测试文件、`46` 个测试通过；`npm run typecheck` 与 `npm run build` 通过。
- focused provider/sector/CLI：`19 passed`。

### 真实 AKShare smoke

在隔离 SQLite cache 上于 2026-07-28 执行：

```bash
python -m fund_agent.cli refresh-market-sector-history \
  --provider akshare --symbols BK1042,BK1036 \
  --output-dir /tmp/ya-fundmind-sector-smoke-live.XWPfQ0 \
  --cache-file /tmp/ya-fundmind-sector-smoke-live.XWPfQ0/funds.sqlite \
  --as-of 2026-07-28
```

- 结果：`success=2`、`fallback=0`、`unavailable=0`。
- `BK1042`（医药商业）与 `BK1036`（半导体）各写入 `4,613` 个有效历史点，范围 `2007-08-01` 至 `2026-07-27`。
- 直接 Provider 验证显示东方财富日线失败后，AKShare `stock_board_industry_index_ths` 对 `BK1042` 的同名“医药商业”成功返回 `19` 个窗口点并写入 cache；AKShare 版本为 `1.18.64`。
- refresh 报告：`/tmp/ya-fundmind-sector-smoke-live.XWPfQ0/market/sector_history_refresh_report.json`。

上述 smoke 是真实网络结果；不将 fixture、旧 cache 或近似板块表述为 live success。

### 浏览器与可访问性基础检查

通过当前分支的本地 Product Web 验证：

- `1440`、`768`、`375` 宽度下页面级 `scrollWidth <= viewport`，没有横向页面溢出。
- 搜索“医药”后，`BK1607` 保留当日行情并显示“历史日线暂未取得”；页面文本不含 `akshare`、`cache`、`normal`、`warning`、`degraded` 等原始诊断词。
- 搜索框具备可访问名称；板块行使用可聚焦按钮，可通过键盘获得焦点；涨跌同时以正负号和颜色表达，非仅依赖颜色。

## 残余限制与后续处理

当东方财富 endpoint 仍不可用、且 AKShare 中不存在完全同名的行业 endpoint 时，该特定板块仍不能保证有历史日线。产品面以空态明确表达，属于可见数据覆盖限制而不是数据真实性错误；它进入 V3 P2，后续需要独立评估官方或授权历史来源，禁止做名称近似映射。

## 边界与回滚

- 主评分：没有修改。
- 主风险：没有修改。
- daily 默认 Provider、watchlist、portfolio 与 scheduler schedule：没有修改。
- 不包含交易、券商、买卖建议或收益承诺。

如需回滚，按独立提交逆序回退行业 endpoint fallback、显式 refresh 与产品空态提交；已存在 cache 点不会被迁移删除。
