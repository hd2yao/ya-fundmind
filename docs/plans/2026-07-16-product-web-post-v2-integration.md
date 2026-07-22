# 产品化 Web Console 发布后集成清单

## 1. 目的

本清单定义 `v2.0.0` Final 发布并完成 post-release ops check 后，如何把 `codex/v2-web-console-next` 中的产品化 Web Console 作为独立版本交付。它避免前端改动污染 `v2.0.0-rc.1` 的真实运行证据，也避免 Final 发布后再次依赖人工提醒才能继续。

候选目标版本为 `v2.1.0`。新增本地 FastAPI/React 产品界面和 `product-web` CLI 属于向后兼容的新增能力，不应以 patch 版本混入 `v2.0.x`；原 Streamlit `web-console` 保持兼容和回退入口。

## 2. 自动恢复条件

同时满足以下条件后，续作监控可以把前端 Draft PR 转入集成流程：

1. `v2.0.0` 已在 clean `main` 上发布并推送 tag。
2. `v2.0.0` post-release ops check 通过。
3. daily/weekly scheduler 仍加载，provider、watchlist、portfolio 和时间配置未发生非预期变化。
4. Draft PR 的 Python、product-web 和前端 CI 均通过。
5. 验收报告仍为 `pass_with_release_dependency`，且没有未处理 P0/P1。

在条件满足前，PR 保持 Draft，不合并、不修改 RC 历史运行 metadata。

## 3. 集成步骤

1. 从远端刷新 `main`，确认 `v2.0.0` tag 与主分支提交关系正确。
2. 在前端分支合入最新 `origin/main`，不 force push、不重写已评审历史。
3. 解决 `pyproject.toml` 和版本文件冲突，建立 `v2.1.0rc1` 候选版本；不得把版本降回 `2.0.0rc1`。
4. 更新 README、CHANGELOG、roadmap/backlog 和独立 release report。
5. 决定静态资源交付方式并完成测试：优先由构建流程生成 `web/dist` 后纳入 Python wheel；源码运行方式继续保留。
6. 重跑第 5 节验证矩阵，完成 focused diff review。
7. 将 PR 转为 ready，等待 CI 与评审通过后合并。
8. 在 clean `main` 上执行安装包 smoke、三视口浏览器验收和 Streamlit 回退检查，再发布 `v2.1.0rc1`。
9. RC 验收没有 P0/P1 后发布 `v2.1.0`，并执行 post-release Web/ops check。

## 4. 必须保持的产品边界

- 不修改主评分和主风险。
- 不改变 daily 默认 provider、watchlist、portfolio 或 scheduler 时间。
- 前端只读取结构化 JSON/API，不解析 Markdown 恢复业务数据。
- Review 仅写有界本地状态；不开放任意路径、命令或 URL。
- 默认只监听 loopback，首版不承诺公网部署、账号体系或多用户并发。
- 不自动交易、不接券商、不输出买卖建议或收益承诺。

## 5. 合并前验证矩阵

### Python 与契约

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli validate-contract --output-dir outputs
python -m fund_agent.cli validate-contract --release-readiness outputs/release/v2_release_readiness.json
```

要求：release-readiness 继续使用内部 strict contract validation；默认测试不访问真实网络；现有 daily、weekly、fixture、AKShare mock、contracts、MCP optional 和 Streamlit 路径不回归。

### Frontend

```bash
cd web
npm ci
npm run typecheck
npm test -- --run
npm run build
```

要求：依赖安装无 audit 漏洞；构建无 chunk size warning；Overview、Market、Watchlist、Portfolio、News、Copilot、Review、Reports 均有 loading/empty/error 状态。

### CLI 与浏览器

```bash
python -m fund_agent.cli web-console --output-dir outputs --dry-run
python -m fund_agent.cli product-web --output-dir outputs --static-dir web/dist --dry-run
```

浏览器必须重新检查 375、768、1440 三个视口，覆盖全部八个路由，并确认：

- 无水平溢出、内容重叠或 console error。
- 移动端关闭侧栏不可聚焦。
- Evidence Drawer 支持 Escape 和焦点恢复。
- degraded/critical、stale/fallback 和缺失值不会显示为健康或真实估值。
- Review 写入仍受 Host、Origin、canonical signal id 和字段长度约束。

### 安装包

在隔离环境安装构建后的 wheel，至少验证：

```bash
fund-agent product-web --output-dir outputs --dry-run
```

若 wheel 中没有可用的静态资源，`v2.1.0` 不得发布；源码目录可运行不能替代安装包验收。

## 6. 回滚策略

产品前端是新增入口，不替换原控制台。发生启动、静态资源、浏览器兼容或 API 回归时：

1. 停止 `product-web` 本地进程。
2. 使用 `python -m fund_agent.cli web-console --output-dir outputs` 回退到 Streamlit。
3. 保留 outputs、runs、dashboard、review state 和 scheduler，不删除研究产物。
4. 回退版本只撤销产品 Web 交付，不修改主评分、主风险或历史运行数据。
5. 根因修复通过独立 patch/RC PR 重新进入验证矩阵。

## 7. 当前已知非阻塞项

- 旧 dashboard 中的相对链接仍依赖原静态目录结构。
- Review state 面向单用户本地进程，没有多进程文件锁。
- 扩展新的文件读取入口前应增加 symlink containment 测试。
- 当前主工作区 portfolio 产物缺少可用当前估值时，页面只能如实显示“暂无数据”。

这些项目不能被误报为已完成，但不会阻塞 `v2.0.0` Final；其中静态资源安装包交付是 `v2.1.0` 发布前的 P1。
