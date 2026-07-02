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
from fund_agent.review_state import list_review_state, summarize_review_state, update_review_state


WEB_CONSOLE_PAGES = (
    "Home",
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
        st.subheader("Market")
        st.json(state["market_report"] or {"status": "missing"})
    with tabs[2]:
        st.subheader("Funds")
        st.json(state["fund_details"] or {"status": "missing"})
    with tabs[3]:
        st.subheader("Portfolio")
        st.json(state["portfolio_report"] or {"status": "missing"})
    with tabs[4]:
        st.subheader("News")
        st.json(state["news_evidence"] or {"status": "missing"})
    with tabs[5]:
        _render_review(st, state_path, state)
    with tabs[6]:
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
