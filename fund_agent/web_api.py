from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from . import __version__


def create_web_app(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
) -> FastAPI:
    """Build the local product Web Console API with fixed filesystem roots."""

    root = Path(output_dir).expanduser().resolve()
    state_path = (
        Path(review_state_path).expanduser().resolve()
        if review_state_path is not None
        else root / "manual_review_state.json"
    )
    app = FastAPI(
        title="YA FundMind OS Local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.output_dir = root
    app.state.review_state_path = state_path

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ready",
            "generator": f"ya-fundmind/{__version__}",
            "local_only": True,
            "output_status": "available" if root.is_dir() else "missing_outputs",
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    return app
