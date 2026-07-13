from pathlib import Path


SKILL = Path("skills/ya-fundmind-research/SKILL.md")


def test_project_research_skill_is_readonly_and_complete() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "TODO" not in text
    assert all(f"`{tool}`" in text for tool in ("status", "catalog", "query", "ask", "evidence"))
    assert "不解析 Markdown" in text
    assert "不修改 watchlist" in text
    assert "不输出买入" in text
    assert "不构成买卖建议" in text
