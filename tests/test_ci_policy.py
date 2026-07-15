from pathlib import Path


def test_default_ci_covers_python_lower_bound_and_primary_runtime() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "matrix.python-version" in workflow
    assert '"3.10"' in workflow
    assert '"3.12"' in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow


def test_default_pytest_has_an_autouse_network_guard() -> None:
    conftest = Path("tests/conftest.py").read_text(encoding="utf-8")

    assert "autouse=True" in conftest
    assert "network access is disabled in default pytest" in conftest
