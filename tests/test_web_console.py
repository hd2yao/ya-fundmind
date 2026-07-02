import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from fund_agent.web_console import (
    WEB_CONSOLE_PAGES,
    build_web_console_state,
    refresh_dashboard_for_web,
    update_review_state_for_web,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeTab:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False



def test_build_web_console_state_reads_ops_status_and_pages(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "weekly_research_summary.json", {"runs_processed": 1})
    _write_json(output_dir / "long_horizon_stability.json", {"enough_history": False, "blockers": ["insufficient_history"]})
    _write_json(output_dir / "news" / "news_evidence_report.json", {"evidence_count": 2, "low_confidence_count": 1})
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1", "signal_id": "s1"}])
    _write_json(output_dir / "manual_review_state.json", {"items": [{"review_id": "r1", "signal_id": "s1", "status": "open"}]})

    state = build_web_console_state(output_dir=output_dir, review_state_path=output_dir / "manual_review_state.json")

    assert "Market" in WEB_CONSOLE_PAGES
    assert "News" in WEB_CONSOLE_PAGES
    assert "Review" in WEB_CONSOLE_PAGES
    assert state["ops_status"]["ops_ready"] is True
    assert state["news_evidence"]["evidence_count"] == 2
    assert state["review_queue_count"] == 1
    assert state["review_state_summary"]["total_review_items"] == 1
    assert state["not_production_model"] is True
    assert state["main_score_changed"] is False
    assert state["main_risk_changed"] is False


def test_refresh_dashboard_for_web_writes_manifest(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "runs" / "2026-06-23" / "daily_research_summary.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "manual_review_state.json", {"items": []})

    manifest = refresh_dashboard_for_web(output_dir=output_dir, days=30)

    assert manifest == output_dir / "dashboard" / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert "news.html" in payload["pages"]


def test_update_review_state_for_web_updates_state(tmp_path):
    output_dir = tmp_path / "outputs"
    state_path = output_dir / "manual_review_state.json"

    item = update_review_state_for_web(
        review_state_path=state_path,
        review_id="r1",
        signal_id="tiantian:return",
        status="needs_more_data",
        note="样本不足",
        reviewer="local",
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert item["status"] == "needs_more_data"
    assert payload["items"][0]["signal_id"] == "tiantian:return"
    assert payload["items"][0]["note"] == "样本不足"


def test_web_console_script_entrypoint_supports_direct_streamlit_execution(monkeypatch, tmp_path):
    fake_streamlit = SimpleNamespace(
        set_page_config=lambda **kwargs: None,
        title=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        button=lambda *args, **kwargs: False,
        tabs=lambda labels: [_FakeTab() for _ in labels],
        subheader=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
        text=lambda *args, **kwargs: None,
        json=lambda *args, **kwargs: None,
        form=lambda *args, **kwargs: _FakeTab(),
        text_input=lambda *args, **kwargs: "",
        selectbox=lambda label, options, **kwargs: options[0],
        text_area=lambda *args, **kwargs: "",
        form_submit_button=lambda *args, **kwargs: False,
        info=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(sys, "argv", ["web_console.py", "--output-dir", str(tmp_path)])

    runpy.run_path(str(Path("fund_agent/web_console.py")), run_name="__main__")
