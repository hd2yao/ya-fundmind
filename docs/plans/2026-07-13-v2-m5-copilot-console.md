# V2 M5 Copilot Console Implementation Plan

## Goal

把 M3 Research Copilot、M2 evidence、数据质量、人工审核和 audit 整合进现有本地 Streamlit Console，保留全部 V1 页面，发布 `v1.5.0`。

## 当前基线

- revision：`97edc19`（`v1.4.0`）。
- baseline server：2026-07-13 12:17:06 +08:00，`http://127.0.0.1:8511`。
- desktop：1440x1000，`/tmp/ya-fundmind-m5-baseline/home-desktop-1440.png`。
- mobile：375x812，`/tmp/ya-fundmind-m5-baseline/home-mobile-375.png`。
- console error：0。

### Baseline Findings

- 首页直接展示 JSON 和完整 Markdown，关键状态难以扫描。
- Run Daily / Refresh 两个动作垂直占位，页面节奏松散。
- 375px 下 tablist 被水平裁切，Reports 不可见。
- Market/Funds/Portfolio/News 主要是原始 `st.json`，没有摘要和空状态层级。
- 尚无 Copilot、citation、data gaps、quality、audit 可视界面。

Baseline Visual Verdict：48/100，结论 `REVISE`。功能可达，但移动导航、信息层级和研究任务闭环未满足 M5。

## Design Contract

### Task Model

- 用户：本机运行 daily/weekly 后复核基金与 ETF 研究材料的个人用户。
- 主要任务：提出一个受约束研究问题，并核对回答、证据、时间和质量。
- 次要任务：查看现有 Market/Funds/Portfolio/News/Reports，维护人工审核状态，查看 audit。
- 非目标：公网、多用户、登录、交易、券商、推荐、复杂可视化编辑器。

### Information Model

Copilot 必须显示：

- question、intent、answer status、as_of、confidence、review_required。
- deterministic summary。
- findings：label、value、quality、code、warnings。
- citations：source、as_of、quality、stale、path、JSON Pointer、excerpt。
- data gaps 和 warnings。
- no-LLM/read-only/不构成买卖建议边界。
- research/MCP audit 的最近脱敏记录。

状态覆盖：empty、loading、answered、partial、unavailable、refused、unsupported、error、review required。

### State Sources

- current answer：`outputs/copilot/research_answer.json`，或本次 `ResearchCopilot.answer()` 返回值。
- current as_of/quality：Research Answer / EvidenceRef，不从页面名称或 Markdown 推断。
- ops ready/latest run：`build_ops_status()`。
- review state：`manual_review_state.json`。
- audit：`outputs/audit/research_queries.jsonl` 和 `outputs/audit/mcp_calls.jsonl`；只显示已脱敏字段。
- main model status：ops artifact；不足历史不得包装成 Console 不可用。

### Layout / Geometry

- 最大内容宽度 1240px，居中；桌面 1440、平板 768、移动 375 均无横向滚动。
- 顶部：产品标题、边界说明、两个紧凑运维动作。
- tablist：允许换行，不做裁切或强制横向画布。
- Copilot：单列流，问题输入在上，回答在下；不依赖移动端并排 columns。
- status metrics 可在桌面并排，移动端允许换行。
- finding 和 citation 使用可展开 section；不使用 card-inside-card。
- 长代码、路径、JSON Pointer 允许换行或横向局部滚动，不能撑开根页面。

### Style / Design Lock

- 方向：quiet operational research console。
- 颜色：白/浅灰 surface、墨色正文、青绿色正常状态、琥珀 warning、红色 refused/critical。
- 字体：系统 sans；标题紧凑，不使用 hero scale；letter spacing 0。
- 组件：细边界、6px 以内圆角、轻阴影仅用于输入焦点，不堆装饰卡片。
- 禁止：渐变、紫色主色、orb/bokeh、营销文案、SVG 插画、超大标题、卡片嵌套。
- 动效：只使用 Streamlit 默认状态反馈，尊重 reduced motion。

## Implementation Tasks

### Task 1：Copilot State / Service

1. RED：页面列表、answer/audit state、坏 JSONL、Copilot write path 和主报告不变测试。
2. 新增 `run_copilot_for_web`、`build_copilot_view_model`、safe JSONL loader。
3. Commit：`feat: add copilot console state service`。

### Task 2：Copilot UI / Existing Pages

1. RED：render semantics、empty/refused/partial/audit 测试。
2. 新增 Copilot tab、question form、summary、finding/citation expander、gaps/warnings、audit。
3. Home 改为结构化 metrics；V1 页面增加摘要和 raw JSON expander。
4. 保留 Review 写入和 Reports 路径。
5. Commit：`feat: add evidence grounded copilot console`。

### Task 3：Responsive Design / Accessibility

1. 注入 scoped CSS：内容宽度、tab wrap、路径换行、status tokens、focus 和 mobile spacing。
2. browser 检查 1440/768/375；回答、refused、empty、Review/Reports 状态。
3. 检查键盘 focus、label、对比、触控尺寸、reduced motion、横向 overflow 和 console errors。
4. Fix loop，直到 Visual Verdict >= 90。
5. Commit：`style: harden copilot console responsiveness`。

### Task 4：Release

1. 更新 README、CHANGELOG、roadmap、tasks、backlog、version、release report。
2. 全量 pytest、compileall、demo/daily/contracts、MCP/Skill、Web dry-run。
3. 新鲜桌面/平板/移动截图和运行身份记录。
4. PR/CI/merge，main 视觉复验后 tag `v1.5.0`。

## Acceptance Gate

- `AC-018` 至 `AC-020` 满足。
- Home/Copilot/Market/Funds/Portfolio/News/Review/Reports 均可访问。
- Copilot 只调用公开 service；不解析 Markdown，不复制业务规则。
- 每个 finding 可展开 citation；缺失和质量问题可见。
- empty/loading/error/refused/unsupported/partial 状态均有明确文案。
- 375/768/1440 无横向页面滚动、裁切、文字重叠或不可达导航。
- 不修改主评分、主风险、provider 默认、watchlist、portfolio、scheduler。
- 不输出买卖建议，不自动交易，不接券商，不承诺收益。

## 实施结果

状态：完成，准备发布 `v1.5.0`。

- Home/Copilot/Market/Funds/Portfolio/News/Review/Reports 均完成结构化展示。
- Copilot 复用公开 service 和共享输出 writer；主报告、主评分和主风险不变。
- 证据引用、质量、缺口、拒绝态和脱敏 audit 已通过单元与真实浏览器验收。
- 修复默认 review state 未跟随 `--output-dir` 的启动路径问题。
- 375/768/1440 根页面 overflow 均为 0；Playwright console 0 errors / 0 warnings。
- Visual Verdict 从基线 48/100 提升到 93/100，结论 `SHIP`。
