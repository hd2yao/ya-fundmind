from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .agents import run_research
from .providers import AkshareProvider, FixtureProvider, ProviderUnavailable, load_portfolio_file
from .report import render_html, render_markdown


DEFAULT_FUNDS_FILE = Path("data/fixtures/funds.json")
DEFAULT_PORTFOLIO_FILE = Path("data/portfolio.example.json")


def _write_reports(result, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "fund_agent_report.md"
    html_path = output_dir / "fund_agent_report.html"
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    html_path.write_text(render_html(result), encoding="utf-8")
    return markdown_path, html_path


def _load_funds(source: str, funds_file: Path):
    if source == "live":
        provider = AkshareProvider()
        return provider.fetch_funds()
    return FixtureProvider(funds_file).fetch_funds()


def _run_report(args) -> int:
    try:
        funds = _load_funds(args.source, args.funds_file)
    except ProviderUnavailable as exc:
        print(f"Live provider unavailable: {exc}")
        return 2

    holdings = None
    if args.portfolio_file:
        holdings = load_portfolio_file(args.portfolio_file)

    result = run_research(
        funds,
        holdings=holdings,
        as_of=args.as_of or date.today().isoformat(),
        candidate_limit=args.limit,
    )
    markdown_path, html_path = _write_reports(result, args.output_dir)
    print(f"Markdown report: {markdown_path}")
    print(f"HTML report: {html_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fund-agent",
        description="基金/ETF 本地投研助手。输出仅用于研究辅助，不构成投资建议。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_report_args(command_parser: argparse.ArgumentParser, *, include_portfolio: bool) -> None:
        command_parser.add_argument("--source", choices=["fixture", "live"], default="fixture")
        command_parser.add_argument("--funds-file", type=Path, default=DEFAULT_FUNDS_FILE)
        command_parser.add_argument(
            "--portfolio-file",
            type=Path,
            default=DEFAULT_PORTFOLIO_FILE if include_portfolio else None,
        )
        command_parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
        command_parser.add_argument("--as-of", default="")
        command_parser.add_argument("--limit", type=int, default=5)

    demo = subparsers.add_parser("demo", help="使用内置样例数据生成报告")
    add_report_args(demo, include_portfolio=True)
    demo.set_defaults(func=_run_report)

    screen = subparsers.add_parser("screen", help="只做基金/ETF 研究优先级筛选")
    add_report_args(screen, include_portfolio=False)
    screen.set_defaults(func=_run_report)

    portfolio = subparsers.add_parser("portfolio", help="分析本地基金/ETF 持仓")
    add_report_args(portfolio, include_portfolio=True)
    portfolio.set_defaults(func=_run_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
