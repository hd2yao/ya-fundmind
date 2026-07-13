# V2 Research Copilot Spec

## 背景和目标

V1 已能稳定生成基金/ETF、市场、组合、新闻、provider trace 和历史 snapshot 等结构化产物，但用户仍需在多个页面和文件之间手工定位事实。V2 需要建立统一、证据驱动的本地研究入口，同时保持 V1 自动运行和只读研究边界。

## 用户场景

- 用户查询当天市场和主题变化，并查看证据来源与数据质量。
- 用户查询某只自选基金的基本情况、历史变化、缺失数据和同类对比。
- 用户查询当前组合的主题暴露、集中度和观察风险。
- 用户查询新闻证据与主题/基金的关联及可信度。
- 用户比较当前与历史 snapshot，理解变化而非只看静态值。
- 用户在数据不足、冲突或过期时知道系统为什么不能给出可靠结论。
- 外部 Agent 通过只读 Skill/MCP 使用同一查询核心。
- 用户在本地 Console 中查看回答、展开证据并完成人工审核。

## 范围

- V1 JSON artifact catalog 和 contract-aware loader。
- 统一 ResearchContext 查询契约。
- EvidenceRef、Evidence Graph 和 quality/conflict gate。
- 受约束的 ResearchAnswer、CLI 和确定性中文 renderer。
- 可选 LLM renderer，默认关闭。
- 只读 Skill/MCP。
- 本地 Copilot Console、人工审核和 audit。
- V2 contract validation、迁移、文档和发布。

## 非目标

- 不自动推荐基金。
- 不输出买卖、仓位、止盈止损或收益承诺。
- 不自动交易、不接券商。
- 不修改 watchlist、portfolio、主评分或主风险。
- 不做 SaaS、多用户、公网部署、移动端或小程序。
- 不让下游解析 Markdown 或任意读取本地文件。
- 不让默认 pytest/CI 依赖真实网络、MCP 服务或 LLM API。

## 验收标准

### 数据访问

- `AC-001`：Artifact Catalog 能发现白名单内的 V1 report、snapshot、trace、market、fund detail、portfolio、news、ops、daily 和 weekly JSON。
- `AC-002`：每个 artifact 描述包含类型、路径、schema、as_of、generated_at、source、quality、stale 和 hash；无法获得的字段安全为空。
- `AC-003`：损坏、缺失、旧 schema 或未知可选字段不会导致整个查询失败，并产生结构化 warning。
- `AC-004`：`research-query` 支持 market、fund、portfolio、news、history 和 quality，且不解析 Markdown/HTML。
- `AC-005`：ResearchContext contract 有 schema version、校验器、兼容性测试和示例。

### 证据和质量

- `AC-006`：关键 finding 至少包含一个可定位到 artifact 和 JSON Pointer 的 EvidenceRef；无证据时不得生成肯定 finding。
- `AC-007`：stale、fallback、critical warning、degraded、样本不足会降低结论质量或阻断结论。
- `AC-008`：来源冲突被并列展示并设置 `review_required=true`，不静默选择单一来源。
- `AC-009`：Evidence Bundle contract 可校验并兼容缺少可选字段的旧产物。

### Copilot

- `AC-010`：`research-ask` 覆盖 market、theme、fund、portfolio、news、history 和 quality intent。
- `AC-011`：无 LLM、无网络、无 secret 时可生成完整 ResearchAnswer JSON 和模板化中文解释。
- `AC-012`：ResearchAnswer 的关键 finding 只能来自已选 evidence，包含 as_of、data gaps、warnings 和 disclaimer。
- `AC-013`：买卖、仓位、收益承诺、交易和券商请求被拒绝或转换为非交易型研究问题。
- `AC-014`：可选 LLM renderer 不能修改数值、证据、quality、review_required 或 guardrail 结果；失败时回退确定性 renderer。

### Skill/MCP

- `AC-015`：Skill/MCP 只暴露 status、catalog、query、ask、evidence 白名单能力，并复用公共服务层。
- `AC-016`：任意路径、路径穿越、写配置、写 outputs 原始 artifact 和交易请求被拒绝。
- `AC-017`：MCP/Skill 调用有脱敏审计，默认安装和 CI 不要求 MCP/LLM optional dependency。

### Console/审核

- `AC-018`：本地 Console 能提交问题、展示 finding、展开 citation、显示 data gaps/quality，并更新人工审核状态。
- `AC-019`：Market、Funds、Portfolio、News、Review、Reports 和 V1 Web Console 功能不回归。
- `AC-020`：Copilot 页面覆盖桌面/移动 viewport、空状态、加载状态、错误状态和无 LLM 状态，不出现重叠或裁切。

### 发布

- `AC-021`：所有 V2 JSON 有 schema version、generated_at、generator 和 contract validation。
- `AC-022`：V1 daily/weekly、fixture、AKShare、dashboard、report、snapshot、trace 和旧 contract 保持兼容。
- `AC-023`：所有默认测试无真实网络，pytest、compileall、contract、CLI e2e、Web、MCP permission tests 通过。
- `AC-024`：daily/weekly scheduler 最近运行成功，P0/P1 为 0，并完成 RC 观察。
- `AC-025`：`main_score_changed=false`、`main_risk_changed=false`，系统不产生交易动作或买卖建议。

## 约束和假设

- Python 3.10+，延续当前标准库优先和可选依赖模式。
- V1 outputs 是事实来源；V2 不从 Markdown/HTML 反向提取事实。
- 核心能力必须在没有 LLM 和 MCP dependency 时可用。
- 新增 schema 优先独立版本，不改变 V1 `schema_version=1.0` 的字段语义。
- 所有用户问题、新闻文本和外部 Agent 输入视为不可信数据。

## 待确认问题

无阻断问题。用户已授权 Codex 在保持安全边界和免费本地默认的前提下自主选择实现细节。
