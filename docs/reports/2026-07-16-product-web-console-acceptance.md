# 产品化 Web Console 验收报告

## 1. 结论

`codex/v2-web-console-next` 已完成产品化本地 Web Console 的首轮实现与验收，结论为 `pass_with_release_dependency`。

- 功能、回归、构建、响应式和基础可访问性检查通过。
- 前端继续保持独立分支，不在 `v2.0.0` Final 发布前合并到 `main`。
- 原 Streamlit `web-console` 继续作为兼容入口和运维回退路径。
- 主评分、主风险、daily 默认 provider、watchlist、portfolio 和 scheduler 均未修改。
- 不自动交易、不接券商、不输出买卖建议或收益承诺。

## 2. 交付范围

### 2.1 页面

| 路由 | 页面 | 验收状态 |
| --- | --- | --- |
| `/` | 研究总览 | 通过 |
| `/market` | 市场情报 | 通过，质量趋势 SVG 已渲染 |
| `/funds` | 自选研究 | 通过，明确标识 watchlist 范围 |
| `/portfolio` | 组合分析 | 通过，缺失估值不伪造收益 |
| `/news` | 新闻证据 | 通过，低置信度和 fixture 有显式标识 |
| `/copilot` | 研究助手 | 通过，只读取本地结构化证据并返回引用 |
| `/review` | 人工审核 | 通过，只写有界本地 review state |
| `/reports` | 报告中心 | 通过，报告下载受固定 allowlist 限制 |

### 2.2 本地服务

- `fund_agent.web_api.create_web_app` 提供固定根目录的 FastAPI read model。
- `python -m fund_agent.cli product-web --output-dir outputs` 启动本地服务。
- 默认只允许 `127.0.0.1`、`localhost`、`::1`，拒绝 `0.0.0.0`。
- SPA fallback 不掩盖未知 `/api/*` 路由。
- 报告下载不能读取 allowlist 之外的本地文件。

## 3. 自动验证

### 3.1 Python

```text
python -m pytest -q
432 passed, 1 skipped in 2.66s

python -m compileall -q fund_agent
exit 0
```

API/CLI 聚焦测试：

```text
python -m pytest -q tests/test_product_web_cli.py tests/test_web_api.py
17 passed in 0.33s
```

### 3.2 Frontend

使用 Node.js `v24.14.0` 执行：

```text
npm ci
found 0 vulnerabilities

npm run typecheck
exit 0

npm test -- --run
10 test files passed, 16 tests passed

npm run build
exit 0
```

生产构建最大分包为 `charts`，约 `357.50 kB`，无 Vite chunk size warning。

### 3.3 CLI 兼容

```text
python -m fund_agent.cli web-console --output-dir outputs --dry-run
ops_ready=True dashboard_ready=True

python -m fund_agent.cli product-web --output-dir outputs --static-dir web/dist --dry-run
api_ready=true static_ready=true
```

两个入口均明确返回：

```text
not_production_model=true
main_score_changed=false
main_risk_changed=false
```

## 4. 浏览器验收

使用主工作区真实 `outputs`，检查 8 个路由与 3 个视口：

- 375 x 812
- 768 x 1024
- 1440 x 1000

共 24 个路由/视口组合，最终结果：

```text
combinations=24
passed=24
failures=[]
console_errors=0
console_warnings=0
```

每个组合均满足：

- HTTP 200。
- 存在唯一页面 H1 和非空 main content。
- 页面无水平溢出。
- 不停留在 loading 状态。
- Market 页面存在实际 Recharts SVG。

初次检查发现 375px 下 Review 长 signal id 将状态标签推出视口。通过允许摘要正文收缩和长词断行修复后，`documentWidth` 从 392px 恢复为 375px，并重新完成全部 24 个组合验收。

## 5. 交互与可访问性

- 移动端导航抽屉可打开，选择 Market 后自动关闭并保留正确焦点。
- 首次 Tab 聚焦“跳到主要内容”，控件进入视口并显示 3px focus ring。
- Review 页面 14 个 button/select/textarea 均有可访问名称或关联 label。
- 页面包含唯一 `main`、唯一 H1 和带“主要导航”名称的 `nav` landmark。
- 主体文本、侧栏导航、次级按钮的实测对比分别为 `14.73:1`、`8.52:1`、`5.68:1`。
- 页面没有需要 alt 的内容图片；图标为装饰时使用 `aria-hidden`，图标按钮提供可访问名称。

## 6. 截图证据

- Desktop Overview：`/Users/dysania/.codex/visualizations/2026/06/22/019eef1d-7df1-7482-aaee-6193b40a8894/ya-fundmind-product-overview-1440.png`
- Tablet Market：`/Users/dysania/.codex/visualizations/2026/06/22/019eef1d-7df1-7482-aaee-6193b40a8894/ya-fundmind-product-market-768.png`
- Mobile Review：`/Users/dysania/.codex/visualizations/2026/06/22/019eef1d-7df1-7482-aaee-6193b40a8894/ya-fundmind-product-review-375.png`

截图属于本地验收证据，不提交到仓库。

## 7. 已知边界

- React 静态产物由 `web/` 构建，当前不打包进 Python wheel；本地源码运行前需要执行 `npm ci && npm run build`。
- 前端只消费现有 JSON contract/Python service，不解析 Markdown，不在浏览器内重算评分。
- 本报告不等于允许合并：必须等 `v2.0.0` Final 发布并完成 post-release ops check，才能将该分支转为可合并 PR。
