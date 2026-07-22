from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_navigation_uses_one_responsive_breakpoint() -> None:
    shell = (ROOT / "web" / "src" / "layout" / "AppShell.tsx").read_text(encoding="utf-8")
    css = (ROOT / "web" / "src" / "styles" / "global.css").read_text(encoding="utf-8")

    assert 'const NARROW_VIEWPORT_QUERY = "(max-width: 960px)"' in shell
    assert "@media (max-width: 960px)" in css
