from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent import __version__
from fund_agent.web_api import create_web_app


def test_health_reports_local_readiness_and_fixed_output_dir(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    app = create_web_app(output_dir=output_dir)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "generator": f"ya-fundmind/{__version__}",
        "local_only": True,
        "output_status": "available",
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }
    assert app.state.output_dir == output_dir.resolve()


def test_health_starts_when_output_dir_is_missing(tmp_path):
    output_dir = tmp_path / "missing"
    app = create_web_app(output_dir=output_dir)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["output_status"] == "missing_outputs"
    assert app.state.output_dir == output_dir.resolve()


def test_app_uses_explicit_review_state_path(tmp_path):
    output_dir = tmp_path / "outputs"
    review_state = tmp_path / "review" / "state.json"

    app = create_web_app(output_dir=output_dir, review_state_path=review_state)

    assert app.state.review_state_path == Path(review_state).resolve()
