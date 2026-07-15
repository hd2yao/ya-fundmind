import tomllib
from pathlib import Path

import fund_agent


def test_package_version_matches_project_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert fund_agent.__version__ == project["project"]["version"]
