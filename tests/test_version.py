import re
from pathlib import Path

import fund_agent


def test_package_version_matches_project_metadata() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)

    assert match is not None
    assert fund_agent.__version__ == match.group(1)
    assert fund_agent.__version__ == "2.1.0"
