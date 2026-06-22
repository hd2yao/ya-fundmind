from fund_agent.cli import main
from fund_agent.cache import FundCache
from fund_agent.models import FundRecord


def test_demo_command_writes_markdown_and_html_reports(tmp_path):
    exit_code = main(["demo", "--output-dir", str(tmp_path), "--as-of", "2026-06-22"])

    markdown = tmp_path / "fund_agent_report.md"
    html = tmp_path / "fund_agent_report.html"

    assert exit_code == 0
    assert markdown.exists()
    assert html.exists()
    assert (tmp_path / "snapshots" / "2026-06-22.json").exists()
    assert "YA FundMind 基金智研系统日报" in markdown.read_text(encoding="utf-8")
    assert "不构成投资建议" in html.read_text(encoding="utf-8")


def test_live_source_failure_returns_nonzero(monkeypatch, tmp_path):
    class FailingProvider:
        def fetch_funds(self):
            raise RuntimeError("network down")

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", lambda: FailingProvider())

    exit_code = main(["screen", "--source", "live", "--output-dir", str(tmp_path)])

    assert exit_code == 2


def test_screen_command_filters_with_watchlist_config(tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        """
funds:
  - code: 510300
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "screen",
            "--watchlist-file",
            str(watchlist),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-22",
        ]
    )

    markdown = (tmp_path / "fund_agent_report.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "510300" in markdown
    assert "000834" not in markdown


def test_portfolio_command_reads_portfolio_config(tmp_path):
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 10
    cost_nav: 3.7
    buy_date: 2026-02-10
    target_weight: 1.0
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "portfolio",
            "--portfolio-config",
            str(portfolio),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-22",
        ]
    )

    markdown = (tmp_path / "fund_agent_report.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "当前市值" in markdown
    assert "510300" in markdown


def test_daily_command_supports_provider_and_config_files(tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        """
funds:
  - code: 510300
""",
        encoding="utf-8",
    )
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 10
    cost_nav: 3.7
    buy_date: 2026-02-10
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "daily",
            "--provider",
            "fixture",
            "--watchlist-file",
            str(watchlist),
            "--portfolio-config",
            str(portfolio),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-22",
        ]
    )

    markdown = (tmp_path / "fund_agent_report.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "数据来源与新鲜度" in markdown
    assert "510300" in markdown
    assert (tmp_path / "snapshots" / "2026-06-22.json").exists()


def test_daily_akshare_provider_can_generate_report_from_cache_fallback(
    monkeypatch, tmp_path
):
    cache_file = tmp_path / "funds.sqlite"
    cache = FundCache(cache_file)
    cache.upsert_funds(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=4.01,
                nav_date="2026-06-21",
                source="akshare",
            )
        ],
        as_of="2026-06-22",
        ttl_days=-1,
    )

    class CacheOnlyProvider:
        def __init__(self, *, cache, **kwargs):
            self.cache = cache

        def fetch_funds(self, *, as_of=None):
            return self.cache.load_funds(as_of=as_of, allow_stale=True)

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", CacheOnlyProvider)

    exit_code = main(
        [
            "daily",
            "--provider",
            "akshare",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-22",
        ]
    )

    markdown = (tmp_path / "fund_agent_report.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "cache:akshare" in markdown
    assert "stale data" in markdown
