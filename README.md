# YA FundMind | 基金智研系统

本项目是第一版本地基金/ETF 投研助手，范围只覆盖基金和 ETF，不做个股推荐，不接券商，不自动下单。

## 能力

- 基金/ETF 研究优先级评分：收益质量、趋势一致性、动量确认、风险调整、反追高惩罚、规模约束。
- 估值分类：场内 ETF/LOF、ETF 联接、QDII 代理、指数/NAV-only、unsupported。
- 持仓分析：当前市值、浮动收益、目标权重偏离、单只集中度、数据新鲜度。
- 报告输出：Markdown + HTML，包含证据标签、估值方式、风险提示和核对清单。
- 无密钥 demo：默认使用 `data/fixtures/funds.json` 和 `data/portfolio.example.json`。

## 快速运行

```bash
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-22
```

输出：

- `outputs/fund_agent_report.md`
- `outputs/fund_agent_report.html`

## 常用命令

```bash
# 只做基金/ETF 筛选
python -m fund_agent.cli screen --output-dir outputs

# 用本地持仓文件分析组合
python -m fund_agent.cli portfolio --portfolio-file data/portfolio.example.json --output-dir outputs

# 可选：尝试 AKShare 实时数据，需要先安装 akshare
python -m fund_agent.cli screen --source live --output-dir outputs
```

## 测试

```bash
python -m pytest -q
```

## 风险边界

本系统输出仅用于研究辅助，不构成投资建议，不承诺收益，不包含任何自动交易指令。基金投资有风险，历史表现不代表未来收益；跨境/QDII 产品还需要额外核对汇率、时区、申赎限制和折溢价。
