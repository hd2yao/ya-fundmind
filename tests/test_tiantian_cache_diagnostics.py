import json
from datetime import datetime, timezone

from fund_agent.cache import FundCache
from fund_agent.cli import main
from fund_agent.models import FundDetail, FundNavPoint


def _seed_tiantian_cache(cache_file, *, ttl_days=30):
    cache = FundCache(cache_file)
    now = datetime(2026, 6, 23, tzinfo=timezone.utc)
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
        ttl_days=ttl_days,
        now=now,
    )
    cache.upsert_nav_points(
        [
            FundNavPoint(code="510300", date="2026-06-21", unit_nav=5.01, source="tiantian"),
            FundNavPoint(code="510300", date="2026-06-22", unit_nav=5.02, source="tiantian"),
            FundNavPoint(code="510300", date="2026-06-23", unit_nav=5.03, source="tiantian"),
        ],
        as_of="2026-06-23",
        ttl_days=ttl_days,
        now=now,
    )


def test_diagnose_tiantian_cache_reports_hit(tmp_path):
    cache_file = tmp_path / "funds.sqlite"
    _seed_tiantian_cache(cache_file)

    exit_code = main(
        [
            "diagnose-tiantian-cache",
            "--code",
            "510300",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    payload = json.loads((tmp_path / "tiantian_cache_diagnostics.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["code"] == "510300"
    assert payload["detail_cache_status"] == "hit"
    assert payload["nav_cache_status"] == "hit"
    assert payload["detail_source"] == "cache:tiantian"
    assert payload["nav_source"] == "cache:tiantian"
    assert payload["nav_points_count"] == 3
    assert payload["latest_nav_date"] == "2026-06-23"
    assert payload["available_windows"] == ["all"]
    assert payload["stale"] is False


def test_diagnose_tiantian_cache_reports_miss(tmp_path, capsys):
    exit_code = main(
        [
            "diagnose-tiantian-cache",
            "--code",
            "510300",
            "--cache-file",
            str(tmp_path / "funds.sqlite"),
            "--output-dir",
            str(tmp_path),
        ]
    )

    payload = json.loads((tmp_path / "tiantian_cache_diagnostics.json").read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 2
    assert payload["detail_cache_status"] == "miss"
    assert payload["nav_cache_status"] == "miss"
    assert "cache miss" in captured.out


def test_diagnose_tiantian_cache_marks_stale(tmp_path):
    cache_file = tmp_path / "funds.sqlite"
    _seed_tiantian_cache(cache_file, ttl_days=-1)

    exit_code = main(
        [
            "diagnose-tiantian-cache",
            "--code",
            "510300",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    payload = json.loads((tmp_path / "tiantian_cache_diagnostics.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["detail_cache_status"] == "stale"
    assert payload["nav_cache_status"] == "stale"
    assert payload["stale"] is True
    assert any(warning["code"] == "stale_cache" for warning in payload["warnings"])
