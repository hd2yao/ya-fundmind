from contextlib import nullcontext

from fund_agent.web_console import _render_copilot


class _Column:
    def __init__(self, st):
        self.st = st

    def metric(self, label, value, **kwargs):
        self.st.records.append(("metric", label, value))


class _FakeStreamlit:
    def __init__(self, *, submitted=False, question=""):
        self.submitted = submitted
        self.question = question
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

    def code(self, value, **kwargs):
        self.records.append(("code", str(value)))

    def info(self, text, **kwargs):
        self.records.append(("info", str(text)))

    def success(self, text, **kwargs):
        self.records.append(("success", str(text)))

    def warning(self, text, **kwargs):
        self.records.append(("warning", str(text)))

    def error(self, text, **kwargs):
        self.records.append(("error", str(text)))

    def form(self, *args, **kwargs):
        return nullcontext()

    def selectbox(self, label, options, **kwargs):
        self.records.append(("selectbox", label))
        return options[0]

    def text_area(self, label, **kwargs):
        self.records.append(("text_area", label))
        return self.question

    def form_submit_button(self, label, **kwargs):
        self.records.append(("submit", label))
        return self.submitted

    def spinner(self, text):
        self.records.append(("spinner", text))
        return nullcontext()

    def columns(self, count):
        size = len(count) if isinstance(count, list) else int(count)
        return [_Column(self) for _ in range(size)]

    def expander(self, label, **kwargs):
        self.records.append(("expander", label))
        return nullcontext()

    def divider(self):
        self.records.append(("divider",))


def _state(answer):
    return {
        "copilot_answer": answer,
        "research_audit": [],
        "mcp_audit": [],
    }


def test_render_answered_copilot_exposes_finding_and_citation(tmp_path) -> None:
    answer = {
        "answer_status": "answered",
        "as_of": "2026-07-13",
        "summary": "已生成证据化回答",
        "confidence": "high",
        "review_required": False,
        "intent": {"intent": "market"},
        "findings": [
            {
                "finding_id": "f1",
                "label": "热门主题",
                "value": ["半导体"],
                "quality_grade": "normal",
                "evidence_ids": ["e1"],
                "warnings": [],
            }
        ],
        "evidence": [
            {
                "evidence_id": "e1",
                "source": "akshare",
                "as_of": "2026-07-13",
                "quality_grade": "normal",
                "stale": False,
                "path": "market/market_intelligence_report.json",
                "json_pointer": "/hot_theme_candidates",
                "excerpt": "半导体",
            }
        ],
        "data_gaps": [],
        "warnings": [],
    }
    st = _FakeStreamlit()

    _render_copilot(st, tmp_path, _state(answer))

    rendered = "\n".join(str(item) for item in st.records)
    assert "Research Copilot" in rendered
    assert "已生成证据化回答" in rendered
    assert "热门主题" in rendered
    assert "market/market_intelligence_report.json" in rendered
    assert "/hot_theme_candidates" in rendered
    assert "不构成买卖建议" in rendered


def test_render_refused_copilot_uses_error_state_and_no_findings(tmp_path) -> None:
    answer = {
        "answer_status": "refused",
        "summary": "该请求涉及交易边界。",
        "confidence": "low",
        "review_required": False,
        "intent": {"intent": "blocked_transaction"},
        "findings": [],
        "evidence": [],
        "data_gaps": [],
        "warnings": ["read_only_boundary_enforced"],
    }
    st = _FakeStreamlit()

    _render_copilot(st, tmp_path, _state(answer))

    assert any(record[0] == "error" and "refused" in record[1] for record in st.records)
    assert not any(record[0] == "expander" and "Finding" in record[1] for record in st.records)


def test_render_empty_copilot_has_actionable_empty_state(tmp_path) -> None:
    st = _FakeStreamlit()

    _render_copilot(st, tmp_path, _state({}))

    assert any(
        record[0] == "info" and "输入研究问题" in record[1]
        for record in st.records
    )


def test_render_copilot_submit_refreshes_state_with_service_result(tmp_path, monkeypatch) -> None:
    st = _FakeStreamlit(submitted=True, question="市场热点如何？")

    class _Answer:
        def __init__(self):
            self.answer_status = "unsupported"

    called = {}

    def fake_run(*, question, output_dir):
        called["question"] = question
        called["output_dir"] = output_dir
        return _Answer()

    monkeypatch.setattr("fund_agent.web_console.run_copilot_for_web", fake_run)
    monkeypatch.setattr(
        "fund_agent.web_console.asdict",
        lambda answer: {
            "answer_status": answer.answer_status,
            "summary": "unsupported",
            "findings": [],
            "evidence": [],
            "data_gaps": ["unsupported_research_topic"],
            "warnings": [],
            "confidence": "low",
            "review_required": False,
            "intent": {"intent": "unsupported"},
        },
        raising=False,
    )

    _render_copilot(st, tmp_path, _state({}))

    assert called == {"question": "市场热点如何？", "output_dir": tmp_path}
    assert any(record[0] == "error" and "unsupported" in record[1] for record in st.records)
