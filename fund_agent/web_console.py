from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
    st.title("YA FundMind Console")
    st.caption("本地投研工作台，仅用于观察和人工审核；不修改主评分/主风险，不构成投资建议。")
    state = build_web_console_state(output_dir=root, review_state_path=state_path)

    if st.button("Run Daily Ops"):
        code = run_daily_ops_for_web(output_dir=root, provider=daily_provider, enable_market_intelligence=True)
        st.info(f"daily ops exit_code={code}")
    if st.button("Refresh Dashboard"):
        manifest = refresh_dashboard_for_web(output_dir=root, review_state_path=state_path)
        st.info(f"dashboard refreshed: {manifest}")

    tabs = st.tabs(list(WEB_CONSOLE_PAGES))
    with tabs[0]:
        _render_home(st, state)
    with tabs[1]:
        st.subheader("Research Copilot")
        st.json(build_copilot_view_model(state["copilot_answer"]))
    with tabs[2]:
        st.subheader("Market")
        st.json(state["market_report"] or {"status": "missing"})
    with tabs[3]:
        st.subheader("Funds")
        st.json(state["fund_details"] or {"status": "missing"})
    with tabs[4]:
        st.subheader("Portfolio")
        st.json(state["portfolio_report"] or {"status": "missing"})
    with tabs[5]:
        st.subheader("News")
        st.json(state["news_evidence"] or {"status": "missing"})
    with tabs[6]:
        _render_review(st, state_path, state)
    with tabs[7]:
        st.subheader("Reports")
        st.json(state["report_paths"])


def _render_home(st, state: dict[str, Any]) -> None:
    status = state["ops_status"]
    st.subheader("Ops Status")
    st.write(
        {
            "ops_ready": status.get("ops_ready"),
            "dashboard_ready": status.get("dashboard_ready"),
            "latest_run": (status.get("latest_run") or {}).get("as_of"),
            "main_model_ready": status.get("main_model_ready"),
        }
    )
    st.subheader("Latest Summary")
    st.text(state.get("latest_summary") or "latest_summary.md 尚未生成")


def _render_review(st, state_path: Path, state: dict[str, Any]) -> None:
    st.subheader("Manual Review")
    st.write(state["review_state_summary"])
    with st.form("manual_review_update"):
        review_id = st.text_input("review_id")
        signal_id = st.text_input("signal_id")
        status = st.selectbox(
            "status",
            [
                "open",
                "needs_more_data",
                "approved_for_more_experiment",
                "rejected",
                "approved_for_main_candidate",
            ],
        )
        reviewer = st.text_input("reviewer")
        note = st.text_area("note")
        submitted = st.form_submit_button("Update Review State")
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
    st.subheader("Queue")
    st.json(state["review_queue"])


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
