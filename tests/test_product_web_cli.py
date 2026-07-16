from pathlib import Path

from fund_agent.cli import main


def _write_static_app(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "index.html").write_text("<!doctype html><title>YA FundMind OS</title>", encoding="utf-8")
    return path


def test_product_web_dry_run_validates_api_and_static_build(tmp_path, capsys):
    output_dir = tmp_path / "outputs"
    static_dir = _write_static_app(tmp_path / "dist")

    exit_code = main(
        [
            "product-web",
            "--output-dir",
            str(output_dir),
            "--static-dir",
            str(static_dir),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Product web ready" in captured.out
    assert "api_ready=true" in captured.out
    assert "static_ready=true" in captured.out
    assert "main_score_changed=false" in captured.out
    assert "main_risk_changed=false" in captured.out


def test_product_web_dry_run_fails_when_static_build_is_missing(tmp_path, capsys):
    exit_code = main(
        [
            "product-web",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--static-dir",
            str(tmp_path / "missing"),
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert "static_ready=false" in capsys.readouterr().out


def test_product_web_rejects_non_loopback_host(tmp_path, capsys):
    static_dir = _write_static_app(tmp_path / "dist")

    exit_code = main(["product-web", "--host", "0.0.0.0", "--static-dir", str(static_dir)])

    assert exit_code == 2
    assert "loopback" in capsys.readouterr().out


def test_product_web_starts_uvicorn_with_fixed_roots(monkeypatch, tmp_path):
    output_dir = tmp_path / "outputs"
    review_state = tmp_path / "review.json"
    static_dir = _write_static_app(tmp_path / "dist")
    calls = []

    monkeypatch.setattr(
        "fund_agent.cli._run_product_web_server",
        lambda **kwargs: calls.append(kwargs) or 0,
    )

    exit_code = main(
        [
            "product-web",
            "--output-dir",
            str(output_dir),
            "--review-state",
            str(review_state),
            "--static-dir",
            str(static_dir),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]
    )

    assert exit_code == 0
    assert calls == [
        {
            "output_dir": output_dir,
            "review_state_path": review_state,
            "static_dir": static_dir,
            "host": "127.0.0.1",
            "port": 8765,
        }
    ]
