import json

from datetime import datetime, timezone
from pathlib import Path

from fund_agent.cli import main
from fund_agent.cache import FundCache
from fund_agent.models import FundDetail, FundNavPoint, FundRecord, ProviderHealth, ProviderWarning


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


def test_smoke_akshare_returns_clear_error_when_provider_unavailable(monkeypatch, tmp_path, capsys):
    class MissingAkshareProvider:
        def __init__(self, **kwargs):
            pass

        available = False
        provider_version = None

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", MissingAkshareProvider)

    exit_code = main(["smoke-akshare", "--output-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "AKShare is not installed" in captured.out
    assert not (tmp_path / "fund_agent_report.json").exists()


def test_default_exit_code_stays_zero_for_degraded_report(monkeypatch, tmp_path):
    class DegradedProvider:
        def __init__(self, **kwargs):
            self.last_health = ProviderHealth(
                provider="akshare",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                warnings=(
                    ProviderWarning(
                        code="stale_cache",
                        message="expired",
                        severity="critical",
                    ),
                ),
            )

        def fetch_funds(self, *, as_of=None):
            return [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)]

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", DegradedProvider)

    exit_code = main(
        [
            "daily",
            "--provider",
            "akshare",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "fund_agent_report.json").exists()


def test_explicit_exit_policy_returns_nonzero_after_writing_degraded_report(monkeypatch, tmp_path):
    provider_config = tmp_path / "providers.yaml"
    provider_config.write_text(
        """
policy:
  fail_on_degraded: true
  fail_on_critical_provider_warning: true
""",
        encoding="utf-8",
    )

    class DegradedProvider:
        def __init__(self, **kwargs):
            self.last_health = ProviderHealth(
                provider="akshare",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                warnings=(
                    ProviderWarning(
                        code="stale_cache",
                        message="expired",
                        severity="critical",
                    ),
                ),
            )

        def fetch_funds(self, *, as_of=None):
            return [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)]

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", DegradedProvider)

    exit_code = main(
        [
            "daily",
            "--provider",
            "akshare",
            "--provider-config",
            str(provider_config),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    assert exit_code == 3
    assert (tmp_path / "fund_agent_report.json").exists()


def test_enrich_fund_tiantian_writes_cache_trace_and_json(monkeypatch, tmp_path):
    class MockTiantianProvider:
        available = True

        def __init__(self, *, cache, **kwargs):
            self.cache = cache
            self.last_health = ProviderHealth(
                provider="tiantian",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                live_row_count=3,
                mapped_row_count=3,
                cache_write_count=3,
            )

        def fetch_fund_detail(self, code, *, as_of=None):
            detail = FundDetail(
                code=code,
                name="沪深300ETF",
                fund_type="ETF",
                fund_company="华泰柏瑞基金",
                fund_manager="张三",
                source="tiantian",
                as_of=as_of,
            )
            self.cache.upsert_fund_details([detail], as_of=as_of)
            return detail

        def fetch_nav_history(self, code, *, start_date=None, end_date=None, as_of=None):
            navs = [
                FundNavPoint(code=code, date="2026-06-21", unit_nav=5.01, source="tiantian"),
                FundNavPoint(code=code, date="2026-06-22", unit_nav=5.02, source="tiantian"),
                FundNavPoint(code=code, date="2026-06-23", unit_nav=5.03, source="tiantian"),
            ]
            self.cache.upsert_nav_points(navs, as_of=as_of or "2026-06-23")
            return navs

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MockTiantianProvider)

    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
            "--nav-windows",
            "1m,3m,all",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "fund_agent_report.json").exists()
    assert (tmp_path / "traces" / "provider-2026-06-23.json").exists()
    payload = json.loads((tmp_path / "fund_agent_report.json").read_text(encoding="utf-8"))
    summary = payload["nav_history_summary"]["510300"]
    assert summary["latest_unit_nav"] == 5.03
    assert "max_drawdown" in summary
    assert set(summary["windows"]) == {"1m", "3m", "all"}
    trace = json.loads((tmp_path / "traces" / "provider-2026-06-23.json").read_text(encoding="utf-8"))
    assert trace["providers"][0]["windows_requested"] == ["1m", "3m", "all"]
    assert trace["providers"][0]["windows_generated"] == ["1m", "3m", "all"]


def test_enrich_fund_rejects_invalid_nav_window(tmp_path, capsys):
    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--output-dir",
            str(tmp_path),
            "--nav-windows",
            "1m,bad",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Unsupported nav window" in captured.out


def test_enrich_fund_allow_cache_uses_tiantian_cache_when_live_unavailable(monkeypatch, tmp_path):
    cache_file = tmp_path / "funds.sqlite"
    cache = FundCache(cache_file)
    cache.upsert_fund_details(
        [
            FundDetail(
                code="510300",
                name="沪深300ETF",
                fund_type="ETF",
                source="tiantian",
                as_of="2026-06-23",
            )
        ],
        as_of="2026-06-23",
        ttl_days=30,
        now=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )
    cache.upsert_nav_points(
        [
            FundNavPoint(code="510300", date="2026-06-21", unit_nav=5.01, source="tiantian"),
            FundNavPoint(code="510300", date="2026-06-23", unit_nav=5.03, source="tiantian"),
        ],
        as_of="2026-06-23",
        ttl_days=30,
        now=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )

    class MissingTiantianProvider:
        available = False

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MissingTiantianProvider)

    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
            "--allow-cache",
        ]
    )

    assert exit_code == 0
    payload = json.loads((tmp_path / "fund_agent_report.json").read_text(encoding="utf-8"))
    assert payload["fund_details"][0]["source"] == "cache:tiantian"
    assert payload["nav_history_summary"]["510300"]["source"] == "cache:tiantian"
    trace = json.loads((tmp_path / "traces" / "provider-2026-06-23.json").read_text(encoding="utf-8"))
    provider = trace["providers"][0]
    assert provider["fallback_used"] is True
    assert provider["fallback_source"] == "cache:tiantian"
    assert provider["cache_read_count"] == 3


def test_enrich_fund_allow_cache_marks_stale_cache(monkeypatch, tmp_path):
    cache_file = tmp_path / "funds.sqlite"
    cache = FundCache(cache_file)
    old_now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    cache.upsert_fund_details(
        [FundDetail(code="510300", name="沪深300ETF", fund_type="ETF", source="tiantian")],
        as_of="2026-06-23",
        ttl_days=-1,
        now=old_now,
    )
    cache.upsert_nav_points(
        [FundNavPoint(code="510300", date="2026-06-23", unit_nav=5.03, source="tiantian")],
        as_of="2026-06-23",
        ttl_days=-1,
        now=old_now,
    )

    class MissingTiantianProvider:
        available = False

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MissingTiantianProvider)

    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
            "--allow-cache",
        ]
    )

    assert exit_code == 0
    trace = json.loads((tmp_path / "traces" / "provider-2026-06-23.json").read_text(encoding="utf-8"))
    assert any(warning["code"] == "stale_cache" for warning in trace["providers"][0]["warnings"])


def test_enrich_fund_allow_cache_miss_returns_clear_error(monkeypatch, tmp_path, capsys):
    class MissingTiantianProvider:
        available = False

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MissingTiantianProvider)

    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--cache-file",
            str(tmp_path / "funds.sqlite"),
            "--output-dir",
            str(tmp_path),
            "--allow-cache",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Tiantian cache fallback missed" in captured.out


def test_enrich_fund_tiantian_unavailable_returns_clear_error(monkeypatch, tmp_path, capsys):
    class MissingTiantianProvider:
        available = False

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MissingTiantianProvider)

    exit_code = main(
        [
            "enrich-fund",
            "--provider",
            "tiantian",
            "--code",
            "510300",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "TiantianFundProvider is not configured" in captured.out


def test_smoke_tiantian_unavailable_returns_clear_error(monkeypatch, tmp_path, capsys):
    class MissingTiantianProvider:
        available = False

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr("fund_agent.cli.TiantianFundProvider", MissingTiantianProvider)

    exit_code = main(["smoke-tiantian", "--code", "510300", "--output-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "TiantianFundProvider is not configured" in captured.out


def test_ci_workflow_has_manual_tiantian_smoke_job():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "run_tiantian_smoke" in workflow
    assert "TIANTIAN_API_BASE_URL" in workflow
    assert "smoke-tiantian" in workflow


def test_generate_signal_candidates_cli_writes_output(tmp_path):
    report = tmp_path / "fund_agent_report.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "as_of": "2026-06-23",
                "data_quality_grade": "normal",
                "provider_health": [],
                "candidates": [{"code": "510300", "name": "沪深300ETF", "category": "ETF"}],
                "valuations": {"510300": {"confidence": "High"}},
                "nav_history_summary": {},
                "fund_details": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "signal_candidates.json"

    exit_code = main(["generate-signal-candidates", "--input", str(report), "--output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "eligible_signals" in payload
    assert payload["summary"]["total_signals"] >= 1
