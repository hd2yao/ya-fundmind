# Local Product Web 运行手册

## 1. 定位

Product Web 是 YA FundMind OS 的本地只读研究界面。FastAPI 读取 daily/weekly 已生成的结构化 JSON，React 页面提供总览、市场、基金探索、组合、新闻、Copilot、审核和报告入口。

- 默认 URL：`http://127.0.0.1:8768`
- 默认监听：仅 `127.0.0.1`
- 默认数据目录：`outputs`
- 服务 label：`com.ya-fundmind.web`
- 不修改主评分、主风险、watchlist、portfolio 或 scheduler。

## 2. 首次安装

```bash
cd /Users/dysania/program/AI/agent/ya-fundmind
python -m pip install -e ".[webapp]"
bash scripts/deploy_local_product_web.sh
bash scripts/install_local_product_web.sh
bash scripts/status_local_product_web.sh
```

安装脚本优先使用项目 `.venv/bin/python`。Web plist 独立于 `com.ya-fundmind.daily` 和 `com.ya-fundmind.weekly`。

## 3. 日常使用

浏览器打开：

```text
http://127.0.0.1:8768
```

daily/weekly 继续更新 `outputs`。API 在请求时读取最新 JSON，Market Intelligence 文件变更后 Fund Explorer 自动重建内存索引，不需要重新构建前端或重启服务。

“全市场”来自 `outputs/market/market_intelligence_report.json`；“我的自选”来自 `configs/watchlist.yaml` 对应的 enrichment 产物。两者都只用于研究观察，不构成买卖建议。

## 4. 代码升级

代码或前端发生变化后执行：

```bash
bash scripts/deploy_local_product_web.sh
```

脚本依次运行 `npm ci`、TypeScript 检查、Vitest、production build 和 Python CLI dry-run。如果 Web LaunchAgent 已安装，脚本会重启并检查 health；未安装时只完成构建验证并给出安装命令。

## 5. 状态和日志

```bash
bash scripts/status_local_product_web.sh
```

检查项：

- plist 是否安装。
- launchctl 是否 loaded。
- `/api/health` 是否可访问。
- SPA 首页是否可访问。

日志：

- `outputs/logs/product-web.out.log`
- `outputs/logs/product-web.err.log`

## 6. 卸载

```bash
bash scripts/uninstall_local_product_web.sh
```

该命令只卸载 Web LaunchAgent，不删除 outputs、cache、runs、dashboard、review state，也不处理 daily/weekly。

## 7. 常见问题

### 页面提示全市场数据缺失

确认 `outputs/market/market_intelligence_report.json` 存在，并运行启用 Market Intelligence 的 daily ops。不要把 fixture 结果误认为真实市场数据。

### CLI 提示 Product web build is missing

执行：

```bash
cd web
npm ci
npm run build
```

构建输出进入 `fund_agent/web_static`，并随 Python wheel 分发。

### 端口被占用

先确认是否已有 `com.ya-fundmind.web` 进程。临时端口可通过 `PRODUCT_WEB_PORT` 配置安装脚本，但正式本地默认仍为 `8768`。

### health 不可访问

查看 stderr 日志，检查 `.venv`、FastAPI/Uvicorn 可选依赖、plist 中 Python 绝对路径和 outputs 权限。不要通过改为 `0.0.0.0` 绕过本地访问边界。

## 8. 延期事项

ChatGPT Sites、公网部署、移动网络访问、账号系统和云端数据同步不属于 `v2.1.0`。在部署边界和数据隐私方案完成前，不上传本地 outputs。
