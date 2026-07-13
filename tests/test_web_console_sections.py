from contextlib import nullcontext

from fund_agent.web_console import (
    _compact_payload,
    _console_css,
    _render_home,
    _render_market,
    _render_review,
    _render_reports,
)


class _Column:
    def __init__(self, st):
        self.st = st

    def metric(self, label, value, **kwargs):
        self.st.records.append(("metric", label, value))


class _FakeStreamlit:
    def __init__(self):
        self.records = []

    def subheader(self, text, **kwargs):
        self.records.append(("subheader", text))

    def caption(self, text, **kwargs):
        self.records.append(("caption", str(text)))

    def markdown(self, text, **kwargs):
        self.records.append(("markdown", str(text)))

    def write(self, value, **kwargs):
        self.records.append(("write", value))

    def json(self, value, **kwargs):
        self.records.append(("json", value))

    def dataframe(self, value, **kwargs):
        self.records.append(("dataframe", value))

    def info(self, text, **kwargs):
        self.records.append(("info", str(text)))

    def warning(self, text, **kwargs):
        self.records.append(("warning", str(text)))

    def success(self, text, **kwargs):
        self.records.append(("success", str(text)))

    def error(self, text, **kwargs):
        self.records.append(("error", str(text)))

    def columns(self, count):
        size = len(count) if isinstance(count, list) else int(count)
        return [_Column(self) for _ in range(size)]

    def expander(self, label, **kwargs):
        self.records.append(("expander", label))
        return nullcontext()

    def form(self, *args, **kwargs):
        return nullcontext()

    def text_input(self, label, **kwargs):
        return ""

    def selectbox(self, label, options, **kwargs):
        return options[0]

    def text_area(self, label, **kwargs):
        return ""

    def form_submit_button(self, label, **kwargs):
        return False


def test_console_css_sets_width_tab_wrap_focus_and_mobile_rules() -> None:
    css = _console_css()

    assert "max-width: 1240px" in css
    assert "flex-wrap: wrap" in css
    assert "tab-highlight" in css
    assert 'aria-selected="true"' in css
    assert ":focus-visible" in css
    assert "summary:focus-visible" in css
    assert "@media (max-width: 640px)" in css
    assert "max-width: 900px" in css
    assert 'data-testid="stMetricValue"' in css
    assert 'data-testid="stColumn"' in css
    assert "prefers-reduced-motion" in css
    assert "gradient" not in css


def test_compact_payload_replaces_large_lists_with_count_and_preview() -> None:
    payload = {"records": [{"code": str(index)} for index in range(20)], "warnings": []}

    compact = _compact_payload(payload, max_items=3)

    assert compact["records"]["count"] == 20
    assert len(compact["records"]["preview"]) == 3
    assert compact["warnings"] == []


def test_home_renders_operational_metrics_and_markdown_summary() -> None:
    st = _FakeStreamlit()
    state = {
        "ops_status": {
            "ops_ready": True,
            "dashboard_ready": True,
            "latest_run": {"as_of": "2026-07-13"},
            "main_model_ready": False,
            "overall_status": "warning",
            "main_model_blockers": ["insufficient_history"],
        },
        "latest_summary": "# Daily Summary\n\n研究产物已生成。",
    }

    _render_home(st, state)

    rendered = "\n".join(str(record) for record in st.records)
    assert "运行状态" in rendered
    assert "2026-07-13" in rendered
    assert "insufficient_history" in rendered
    assert "研究产物已生成" in rendered


def test_market_renders_summary_and_only_compact_raw_payload() -> None:
    st = _FakeStreamlit()
    report = {
        "as_of": "2026-07-13",
        "source": "akshare",
        "total_funds": 100,
        "total_etfs": 20,
        "themes": [{"name": "半导体"}],
        "hot_theme_candidates": [{"theme": "半导体", "score": 3.2}],
        "records": [{"code": str(index)} for index in range(50)],
        "warnings": [],
    }

    _render_market(st, report)

    rendered = "\n".join(str(record) for record in st.records)
    assert "Market Intelligence" in rendered
    assert "半导体" in rendered
    json_payload = next(record[1] for record in st.records if record[0] == "json")
    assert json_payload["records"]["count"] == 50
    assert len(json_payload["records"]["preview"]) == 5


def test_reports_marks_available_and_missing_paths(tmp_path) -> None:
    existing = tmp_path / "report.html"
    existing.write_text("ok", encoding="utf-8")
    st = _FakeStreamlit()

    _render_reports(st, {"report": str(existing), "missing": str(tmp_path / "missing.json")})

    rows = next(record[1] for record in st.records if record[0] == "dataframe")
    assert rows[0]["status"] == "available"
    assert rows[1]["status"] == "missing"


def test_review_renders_summary_metrics_and_queue_preview(tmp_path) -> None:
    st = _FakeStreamlit()
    state = {
        "review_state_summary": {
            "total_review_items": 2,
            "unresolved_count": 1,
            "needs_more_data_count": 1,
            "approved_count": 1,
        },
        "review_queue": [{"review_id": "r1", "status": "open"}],
        "review_state": [{"review_id": "r2", "status": "approved_for_more_experiment"}],
    }

    _render_review(st, tmp_path / "review.json", state)

    rendered = "\n".join(str(record) for record in st.records)
    assert "待审核" in rendered
    assert "需要更多数据" in rendered
    assert any(record[0] == "dataframe" for record in st.records)
