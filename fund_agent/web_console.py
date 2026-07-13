from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Streamlit runs this file as a script path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fund_agent.evidence_dashboard import generate_evidence_dashboard
from fund_agent.ops import build_ops_status
from fund_agent.research_copilot import ResearchCopilot
from fund_agent.research_output import write_research_answer_outputs
from fund_agent.review_state import list_review_state, summarize_review_state, update_review_state


WEB_CONSOLE_PAGES = (
    "Home",
    "Copilot",
    "Market",
    "Funds",
    "Portfolio",
    "News",
    "Review",
    "Reports",
)


def build_web_console_state(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    state_path = Path(review_state_path) if review_state_path else root / "manual_review_state.json"
    review_state = list_review_state(state_path)
    review_queue = _load_json(root / "manual_review_queue.json", default=[])
    if not isinstance(review_queue, list):
        review_queue = []
    return {
        "output_dir": str(root),
        "pages": list(WEB_CONSOLE_PAGES),
        "ops_status": build_ops_status(root),
        "latest_summary": _read_text(root / "latest_summary.md"),
        "latest_summary_data": _load_json(root / "latest_summary.json"),
        "review_queue": review_queue,
        "review_queue_count": len(review_queue),
        "review_state": review_state,
        "review_state_summary": summarize_review_state(review_state),
        "market_report": _load_json(root / "market" / "market_intelligence_report.json"),
        "fund_details": _load_json(root / "fund_details" / "watchlist_fund_details.json"),
        "portfolio_report": _load_json(root / "portfolio" / "portfolio_report.json"),
        "news_evidence": _load_json(root / "news" / "news_evidence_report.json"),
        "copilot_answer": _load_json(root / "copilot" / "research_answer.json"),
        "research_audit": _load_audit_events(
            root / "audit" / "research_queries.jsonl",
            event_type="research",
        ),
        "mcp_audit": _load_audit_events(
            root / "audit" / "mcp_calls.jsonl",
            event_type="mcp",
        ),
        "report_paths": _report_paths(root),
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def refresh_dashboard_for_web(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
    days: int = 30,
) -> Path:
    root = Path(output_dir)
    state_path = Path(review_state_path) if review_state_path else root / "manual_review_state.json"
    return generate_evidence_dashboard(
        runs_dir=root / "runs",
        review_state_path=state_path,
        output_dir=root / "dashboard",
        days=days,
    )


def update_review_state_for_web(
    *,
    review_state_path: Path | str,
    review_id: str,
    status: str,
    note: str = "",
    reviewer: str = "",
    signal_id: str | None = None,
) -> dict[str, Any]:
    return update_review_state(
        state_path=review_state_path,
        review_id=review_id,
        signal_id=signal_id,
        status=status,
        note=note,
        reviewer=reviewer,
    )


def run_daily_ops_for_web(
    *,
    output_dir: Path | str = Path("outputs"),
    provider: str = "fixture",
    enable_market_intelligence: bool = True,
) -> int:
    env = os.environ.copy()
    env["OUTPUT_DIR"] = str(output_dir)
    env["PROVIDER"] = provider
    env["ENABLE_MARKET_INTELLIGENCE"] = "true" if enable_market_intelligence else "false"
    result = subprocess.run(["bash", "scripts/run_daily_ops.sh"], check=False, env=env)
    return int(getattr(result, "returncode", result if isinstance(result, int) else 0))


def run_copilot_for_web(
    *,
    question: str,
    output_dir: Path | str = Path("outputs"),
):
    root = Path(output_dir)
    answer = ResearchCopilot(root).answer(question)
    write_research_answer_outputs(answer, root)
    return answer


def build_copilot_view_model(answer: dict[str, Any] | None) -> dict[str, Any]:
    payload = answer if isinstance(answer, dict) else {}
    if not payload:
        return {
            "status": "empty",
            "tone": "neutral",
            "summary": "尚未生成 Research Copilot 回答。",
            "as_of": None,
            "intent": "--",
            "confidence": "--",
            "review_required": False,
            "finding_count": 0,
            "evidence_count": 0,
            "findings": [],
            "data_gaps": [],
            "warnings": [],
        }
    status = str(payload.get("answer_status") or "unavailable")
    evidence_items = [item for item in payload.get("evidence") or [] if isinstance(item, dict)]
    evidence_by_id = {
        str(item.get("evidence_id")): item
        for item in evidence_items
        if item.get("evidence_id")
    }
    findings = []
    for finding in payload.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        findings.append(
            {
                **finding,
                "citations": [
                    evidence_by_id[evidence_id]
                    for evidence_id in finding.get("evidence_ids") or []
                    if evidence_id in evidence_by_id
                ],
            }
        )
    return {
        "status": status,
        "tone": _copilot_tone(status),
        "summary": str(payload.get("summary") or "没有可用研究摘要。"),
        "as_of": payload.get("as_of"),
        "intent": (payload.get("intent") or {}).get("intent") or "--",
        "confidence": payload.get("confidence") or "low",
        "review_required": bool(payload.get("review_required")),
        "finding_count": len(findings),
        "evidence_count": len(evidence_items),
        "findings": findings,
        "data_gaps": list(payload.get("data_gaps") or []),
        "warnings": list(payload.get("warnings") or []),
    }


def render_streamlit_app(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
    daily_provider: str = "fixture",
) -> None:
    import streamlit as st

    root = Path(output_dir)
    state_path = Path(review_state_path) if review_state_path else root / "manual_review_state.json"
    st.set_page_config(page_title="YA FundMind Console", layout="wide")
    _inject_console_styles(st)
    st.title("YA FundMind OS")
    st.caption("本地投研工作台，仅用于观察和人工审核；不修改主评分/主风险，不构成投资建议。")
    state = build_web_console_state(output_dir=root, review_state_path=state_path)

    action_columns = st.columns([1.4, 1.4, 5.2])
    if action_columns[0].button("Run Daily", use_container_width=True):
        code = run_daily_ops_for_web(output_dir=root, provider=daily_provider, enable_market_intelligence=True)
        st.info(f"daily ops exit_code={code}")
    if action_columns[1].button("Refresh", use_container_width=True):
        manifest = refresh_dashboard_for_web(output_dir=root, review_state_path=state_path)
        st.info(f"dashboard refreshed: {manifest}")

    tabs = st.tabs(list(WEB_CONSOLE_PAGES))
    with tabs[0]:
        _render_home(st, state)
    with tabs[1]:
        _render_copilot(st, root, state)
    with tabs[2]:
        _render_market(st, state["market_report"])
    with tabs[3]:
        _render_funds(st, state["fund_details"])
    with tabs[4]:
        _render_portfolio(st, state["portfolio_report"])
    with tabs[5]:
        _render_news(st, state["news_evidence"])
    with tabs[6]:
        _render_review(st, state_path, state)
    with tabs[7]:
        _render_reports(st, state["report_paths"])


def _render_copilot(st, root: Path, state: dict[str, Any]) -> None:
    st.subheader("Research Copilot")
    st.caption("基于本地 JSON 研究产物回答，并为每项结论附上可追溯证据。")

    examples = (
        "选择一个示例，或在下方输入自己的研究问题",
        "当前市场热点和主要证据是什么？",
        "自选基金中哪些数据需要人工复核？",
        "当前组合有哪些已知的数据缺口？",
    )
    with st.form("research_copilot_query"):
        example = st.selectbox("研究问题示例", examples)
        question = st.text_area(
            "研究问题",
            placeholder="例如：当前市场热点和主要证据是什么？",
            height=96,
        )
        submitted = st.form_submit_button("生成证据化回答")

    if submitted:
        selected_question = question.strip()
        if not selected_question and example != examples[0]:
            selected_question = example
        if not selected_question:
            st.warning("请输入研究问题，或选择一个示例问题。")
        else:
            try:
                with st.spinner("正在读取本地研究证据……"):
                    answer = run_copilot_for_web(question=selected_question, output_dir=root)
                state["copilot_answer"] = asdict(answer)
                state["research_audit"] = _load_audit_events(
                    root / "audit" / "research_queries.jsonl",
                    event_type="research",
                )
            except Exception as exc:  # pragma: no cover - Streamlit boundary protection
                st.error(f"Research Copilot 运行失败：{type(exc).__name__}: {exc}")

    view = build_copilot_view_model(state.get("copilot_answer"))
    columns = st.columns(4)
    columns[0].metric("回答状态", view["status"])
    columns[1].metric("研究意图", _metric_intent(view["intent"]))
    columns[2].metric("置信度", view["confidence"])
    columns[3].metric("证据数量", view["evidence_count"])
    st.caption(
        " · ".join(
            (
                f"as_of={view['as_of'] or '--'}",
                f"review_required={view['review_required']}",
                f"intent={view['intent']}",
            )
        )
    )

    status = view["status"]
    if status == "empty":
        st.info("输入研究问题后，将在这里显示结论、证据引用和数据缺口。")
    elif status == "answered":
        st.success("status=answered：本地证据足以形成研究回答。")
    elif status in {"partial", "unavailable"}:
        st.warning(f"status={status}：证据不完整，请结合数据缺口人工复核。")
    elif status in {"refused", "unsupported"}:
        st.error(f"status={status}：请求超出只读投研边界或当前能力范围。")
    else:
        st.info(f"status={status}")

    st.markdown("**研究摘要**")
    st.write(view["summary"])

    for index, finding in enumerate(view["findings"], start=1):
        label = str(finding.get("label") or finding.get("finding_id") or "未命名结论")
        with st.expander(f"Finding {index} · {label}", expanded=index == 1):
            st.write(finding.get("value"))
            quality = finding.get("quality_grade") or "unknown"
            st.caption(f"quality_grade={quality}")
            for warning in finding.get("warnings") or []:
                st.warning(str(warning))

            citations = finding.get("citations") or []
            if citations:
                st.markdown("**证据引用**")
            for citation in citations:
                evidence_id = citation.get("evidence_id") or "evidence"
                source = citation.get("source") or "unknown"
                st.markdown(f"**{evidence_id} · {source}**")
                st.caption(
                    " · ".join(
                        (
                            f"as_of={citation.get('as_of') or '--'}",
                            f"quality={citation.get('quality_grade') or 'unknown'}",
                            f"stale={bool(citation.get('stale'))}",
                        )
                    )
                )
                path = citation.get("path") or "--"
                pointer = citation.get("json_pointer") or ""
                st.code(f"{path}#{pointer}")
                if citation.get("excerpt") not in {None, ""}:
                    st.write(citation["excerpt"])

    if view["data_gaps"]:
        st.markdown("**数据缺口**")
        for gap in view["data_gaps"]:
            st.warning(str(gap))
    if view["warnings"]:
        st.markdown("**边界与质量警告**")
        for warning in view["warnings"]:
            st.warning(str(warning))

    if state.get("research_audit"):
        with st.expander("最近研究审计（脱敏）"):
            st.json(state["research_audit"][-10:])

    st.divider()
    st.caption("仅用于研究观察和人工审核，不改变主评分/主风险，不构成买卖建议。")


def _render_home(st, state: dict[str, Any]) -> None:
    status = state["ops_status"]
    st.subheader("运行状态")
    columns = st.columns(4)
    columns[0].metric("Daily Ops", "Ready" if status.get("ops_ready") else "Blocked")
    columns[1].metric("Dashboard", "Ready" if status.get("dashboard_ready") else "Missing")
    columns[2].metric("最新研究日", (status.get("latest_run") or {}).get("as_of") or "--")
    columns[3].metric("主模型门禁", "Ready" if status.get("main_model_ready") else "Research only")

    overall_status = str(status.get("overall_status") or "unknown")
    blockers = [str(item) for item in status.get("main_model_blockers") or []]
    if status.get("ops_ready"):
        st.success(f"overall_status={overall_status}：日常研究与展示链路可用。")
    else:
        st.error(f"overall_status={overall_status}：运行链路需要检查。")
    if blockers:
        st.warning("主模型仍受门禁限制：" + ", ".join(blockers))

    st.subheader("最新摘要")
    summary = state.get("latest_summary") or "latest_summary.md 尚未生成"
    summary_data = state.get("latest_summary_data") or {}
    if summary_data:
        columns = st.columns(4)
        columns[0].metric("Daily 状态", (summary_data.get("daily") or {}).get("status") or "--")
        columns[1].metric(
            "数据质量",
            (summary_data.get("daily") or {}).get("data_quality_grade") or "--",
        )
        columns[2].metric(
            "市场历史样本",
            _format_number(summary_data.get("latest_market_snapshots_processed")),
        )
        columns[3].metric(
            "Weekly 有效 Runs",
            _format_number((summary_data.get("weekly") or {}).get("runs_processed")),
        )
        st.markdown("**当前研究覆盖**")
        coverage_columns = st.columns(3)
        coverage_columns[0].metric(
            "市场主题",
            _format_number(summary_data.get("latest_market_theme_count")),
        )
        coverage_columns[1].metric(
            "自选详情",
            _format_number(summary_data.get("watchlist_detail_count")),
        )
        coverage_columns[2].metric(
            "组合持仓",
            _format_number(summary_data.get("latest_portfolio_holding_count")),
        )
        explanation = summary_data.get("main_model_blocker_explanation")
        if explanation:
            st.caption(str(explanation))
        with st.expander("完整运行摘要"):
            st.markdown(summary)
    else:
        st.markdown(summary)


def _render_market(st, report: dict[str, Any] | None) -> None:
    st.subheader("Market Intelligence")
    if not report:
        st.info("市场情报产物尚未生成。")
        return
    st.caption(f"as_of={report.get('as_of') or '--'} · source={report.get('source') or '--'}")
    columns = st.columns(4)
    columns[0].metric("基金样本", _format_number(report.get("total_funds")))
    columns[1].metric("ETF 样本", _format_number(report.get("total_etfs")))
    columns[2].metric("主题数量", _format_number(len(report.get("themes") or [])))
    columns[3].metric("热点候选", _format_number(len(report.get("hot_theme_candidates") or [])))
    _render_warnings(st, report.get("warnings"))
    candidates = _tabular_preview(report.get("hot_theme_candidates"), limit=20)
    if candidates:
        st.markdown("**热点候选（研究观察）**")
        st.dataframe(candidates, use_container_width=True, hide_index=True)
    else:
        st.info("当前没有可展示的热点候选。")
    _render_compact_source(st, report)


def _render_funds(st, report: dict[str, Any] | None) -> None:
    st.subheader("Watchlist Fund Details")
    if not report:
        st.info("自选基金详情产物尚未生成。")
        return
    coverage = report.get("coverage_summary") or {}
    st.caption(f"as_of={report.get('as_of') or '--'} · 当前页仅展示自选池补充数据")
    columns = st.columns(4)
    columns[0].metric("详情数量", _format_number(report.get("detail_count")))
    columns[1].metric("缺失数量", _format_number(report.get("missing_count")))
    columns[2].metric("质量警告", _format_number(report.get("warning_count")))
    columns[3].metric("字段覆盖率", _format_ratio(_first_value(coverage, "average_coverage_ratio", "coverage_ratio")))
    details = _tabular_preview(report.get("fund_details"), limit=20)
    if details:
        st.dataframe(details, use_container_width=True, hide_index=True)
    else:
        st.info("当前没有可展示的基金详情。")
    _render_compact_source(st, report)


def _render_portfolio(st, report: dict[str, Any] | None) -> None:
    st.subheader("Portfolio Observation")
    if not report:
        st.info("组合分析产物尚未生成；空配置属于可接受状态。")
        return
    st.caption(f"{report.get('portfolio_name') or '未命名组合'} · as_of={report.get('as_of') or '--'}")
    columns = st.columns(4)
    columns[0].metric("持仓数量", _format_number(report.get("holding_count")))
    columns[1].metric("组合估值", _format_money(report.get("total_value")))
    columns[2].metric("可用现金", _format_money(report.get("cash_available")))
    columns[3].metric("观察问题", _format_number(report.get("observation_issue_count")))
    if str(report.get("status") or "") == "warning":
        st.warning("组合状态为 warning；这里只展示观察结果，不改变主风险。")
    _render_warnings(st, report.get("warnings"))
    positions = _tabular_preview(report.get("positions"), limit=20)
    if positions:
        st.markdown("**持仓观察**")
        st.dataframe(positions, use_container_width=True, hide_index=True)
    issues = _tabular_preview(report.get("observation_issues"), limit=20)
    if issues:
        st.markdown("**观察问题**")
        st.dataframe(issues, use_container_width=True, hide_index=True)
    _render_compact_source(st, report)


def _render_news(st, report: dict[str, Any] | None) -> None:
    st.subheader("News Evidence")
    if not report:
        st.info("新闻与公告证据产物尚未生成；未配置来源时允许为空。")
        return
    st.caption(f"as_of={report.get('as_of') or '--'} · source={report.get('source') or '--'}")
    columns = st.columns(4)
    columns[0].metric("证据数量", _format_number(report.get("evidence_count")))
    columns[1].metric("低置信证据", _format_number(report.get("low_confidence_count")))
    columns[2].metric("去重数量", _format_number(report.get("duplicate_count")))
    columns[3].metric("覆盖主题", _format_number(len(report.get("by_theme") or {})))
    _render_warnings(st, report.get("warnings"))
    items = _tabular_preview(report.get("items"), limit=30)
    if items:
        st.dataframe(items, use_container_width=True, hide_index=True)
    else:
        st.info("当前没有可展示的新闻或公告证据。")
    _render_compact_source(st, report)


def _render_reports(st, report_paths: dict[str, str]) -> None:
    st.subheader("Reports & Artifacts")
    st.caption("机器读取应使用 JSON contract；HTML/Markdown 仅供人工查看。")
    rows = []
    for name, raw_path in report_paths.items():
        path = Path(raw_path)
        rows.append(
            {
                "artifact": name,
                "status": "available" if path.exists() and path.is_file() else "missing",
                "path": str(path),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_warnings(st, warnings: Any) -> None:
    for warning in warnings or []:
        st.warning(str(warning))


def _render_compact_source(st, payload: dict[str, Any]) -> None:
    with st.expander("Source JSON preview"):
        st.json(_compact_payload(payload, max_items=5))


def _compact_payload(value: Any, *, max_items: int = 5) -> Any:
    if isinstance(value, dict):
        return {key: _compact_payload(item, max_items=max_items) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > max_items:
            return {
                "count": len(value),
                "preview": [
                    _compact_payload(item, max_items=max_items) for item in value[:max_items]
                ],
            }
        return [_compact_payload(item, max_items=max_items) for item in value]
    return value


def _tabular_preview(value: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            rows.append({"value": item})
            continue
        rows.append(
            {
                key: json.dumps(field, ensure_ascii=False) if isinstance(field, (dict, list)) else field
                for key, field in item.items()
            }
        )
    return rows


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    return None


def _format_number(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "--"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _format_money(value: Any) -> str:
    if value is None:
        return "--"
    try:
        return f"¥{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_ratio(value: Any) -> str:
    if value is None:
        return "--"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if 0 <= number <= 1:
        number *= 100
    return f"{number:.1f}%"


def _metric_intent(intent: Any) -> str:
    value = str(intent or "--")
    aliases = {
        "blocked_transaction": "blocked",
        "data_quality": "quality",
    }
    return aliases.get(value, value)


def _inject_console_styles(st) -> None:
    st.markdown(_console_css(), unsafe_allow_html=True)


def _console_css() -> str:
    return """
<style>
:root {
  --fundmind-ink: #17201f;
  --fundmind-muted: #5f6b69;
  --fundmind-line: #d7ddda;
  --fundmind-surface: #ffffff;
  --fundmind-accent: #0f766e;
  --fundmind-warning: #9a6700;
}
[data-testid="stAppViewContainer"] {
  background: #f4f6f5;
  color: var(--fundmind-ink);
}
[data-testid="stDecoration"] {
  display: none;
}
.block-container {
  max-width: 1240px;
  padding-top: 1.75rem;
  padding-bottom: 3rem;
}
h1, h2, h3, p, label, button, input, textarea {
  letter-spacing: 0 !important;
}
h1 {
  font-size: 2rem !important;
  line-height: 1.2 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  flex-wrap: wrap;
  gap: 0.25rem 0.5rem;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  min-height: 44px;
  padding: 0.55rem 0.75rem;
  border-bottom: 2px solid transparent;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
  color: var(--fundmind-accent) !important;
  border-bottom-color: var(--fundmind-accent);
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
  display: none;
}
[data-testid="stMetric"] {
  border-left: 3px solid var(--fundmind-accent);
  padding-left: 0.75rem;
}
[data-testid="stMetricLabel"] {
  color: var(--fundmind-muted);
}
[data-testid="stMetricValue"] > div {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  overflow-wrap: anywhere;
  line-height: 1.15;
}
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
  min-height: 44px;
  border-radius: 6px;
  border-color: #aeb9b5;
  color: var(--fundmind-ink);
  background: var(--fundmind-surface);
}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  border-color: var(--fundmind-accent);
  color: var(--fundmind-accent);
}
button:focus-visible,
input:focus-visible,
textarea:focus-visible,
[data-testid="stExpander"] summary:focus-visible,
[role="tab"]:focus-visible {
  outline: 3px solid #0f766e !important;
  outline-offset: 2px;
}
pre, code, [data-testid="stCodeBlock"] {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--fundmind-line);
  border-radius: 6px;
}
@media (min-width: 641px) and (max-width: 900px) {
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
  }
  [data-testid="stColumn"] {
    min-width: 15rem !important;
    flex: 1 1 15rem !important;
  }
}
@media (max-width: 640px) {
  .block-container {
    padding: 1rem 0.85rem 2rem;
  }
  h1 {
    font-size: 1.6rem !important;
  }
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
  }
  [data-testid="stColumn"] {
    min-width: min(100%, 9rem) !important;
    flex: 1 1 9rem !important;
  }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
</style>
"""


def _render_review(st, state_path: Path, state: dict[str, Any]) -> None:
    st.subheader("Manual Review")
    st.caption("人工审核只更新 review state，不修改主评分、主风险或研究产物。")
    summary = state["review_state_summary"]
    columns = st.columns(4)
    columns[0].metric("审核记录", _format_number(summary.get("total_review_items")))
    columns[1].metric("待审核", _format_number(summary.get("unresolved_count")))
    columns[2].metric("需要更多数据", _format_number(summary.get("needs_more_data_count")))
    columns[3].metric("已通过实验", _format_number(summary.get("approved_count")))

    st.markdown("**更新审核状态**")
    with st.form("manual_review_update"):
        review_id = st.text_input("Review ID")
        signal_id = st.text_input("Signal ID（可选）")
        status = st.selectbox(
            "审核状态",
            [
                "open",
                "needs_more_data",
                "approved_for_more_experiment",
                "rejected",
                "approved_for_main_candidate",
            ],
        )
        reviewer = st.text_input("Reviewer")
        note = st.text_area("审核备注")
        submitted = st.form_submit_button("保存审核状态")
    if submitted and review_id:
        item = update_review_state_for_web(
            review_state_path=state_path,
            review_id=review_id,
            signal_id=signal_id or None,
            status=status,
            reviewer=reviewer,
            note=note,
        )
        st.success(f"updated {item['review_id']}")

    st.markdown("**审核队列**")
    queue = _tabular_preview(state["review_queue"], limit=50)
    if queue:
        st.dataframe(queue, use_container_width=True, hide_index=True)
    else:
        st.info("当前审核队列为空。")

    review_items = _tabular_preview(state.get("review_state"), limit=50)
    if review_items:
        st.markdown("**最近审核状态**")
        st.dataframe(review_items, use_container_width=True, hide_index=True)
    with st.expander("完整审核状态"):
        st.json(_compact_payload(state.get("review_state") or [], max_items=20))


def _report_paths(root: Path) -> dict[str, str]:
    paths = {
        "latest_summary": root / "latest_summary.md",
        "fund_agent_report": root / "fund_agent_report.html",
        "dashboard": root / "dashboard" / "index.html",
        "market": root / "dashboard" / "market.html",
        "funds": root / "dashboard" / "funds.html",
        "portfolio": root / "dashboard" / "portfolio.html",
        "news": root / "dashboard" / "news.html",
        "review": root / "dashboard" / "review.html",
    }
    return {key: str(path) for key, path in paths.items()}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {} if default is None else default


def _load_audit_events(path: Path, *, event_type: str, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if event_type == "research":
            events.append(_research_audit_view(item))
        elif event_type == "mcp":
            events.append(_mcp_audit_view(item))
    return events[-limit:]


def _research_audit_view(item: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "timestamp",
        "question_hash",
        "question_preview",
        "intent",
        "answer_status",
        "finding_count",
        "evidence_count",
        "data_gap_count",
        "warning_count",
        "review_required",
    )
    return {field: item.get(field) for field in fields if field in item}


def _mcp_audit_view(item: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "timestamp",
        "tool",
        "status",
        "duration_ms",
        "result_status",
        "result_counts",
        "error_code",
    )
    result = {field: item.get(field) for field in fields if field in item}
    arguments = item.get("argument_summary")
    if isinstance(arguments, dict):
        safe_fields = (
            "question_hash",
            "question_preview",
            "topic",
            "code",
            "artifact_type",
            "limit",
            "unknown_argument_count",
        )
        result["argument_summary"] = {
            field: arguments.get(field) for field in safe_fields if field in arguments
        }
    return result


def _copilot_tone(status: str) -> str:
    if status == "answered":
        return "normal"
    if status in {"partial", "unavailable"}:
        return "warning"
    if status in {"refused", "unsupported"}:
        return "critical"
    return "neutral"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YA FundMind local Streamlit console")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--review-state", type=Path)
    parser.add_argument("--daily-provider", default="fixture")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    render_streamlit_app(
        output_dir=args.output_dir,
        review_state_path=args.review_state,
        daily_provider=args.daily_provider,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
