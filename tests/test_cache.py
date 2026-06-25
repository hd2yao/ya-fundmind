from datetime import datetime, timedelta, timezone

from fund_agent.cache import FundCache
from fund_agent.models import FundDetail, FundNavPoint, FundRecord


def test_cache_initializes_expected_tables(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")

    table_names = cache.table_names()

    assert {"fund_basics", "fund_navs", "fund_valuations", "fund_details"} <= table_names


def test_cache_round_trips_fund_records(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    fund = FundRecord(
        code=" 510300 ",
        name="沪深300ETF",
        category="ETF",
        nav=4.01,
        nav_date="2026-06-21",
        returns={"1m": 3.2, "3m": 7.8},
        scale_billion=460.0,
        manager="华泰柏瑞基金",
        fee_rate=0.6,
        exchange_traded=True,
        price=4.05,
        target_etf="",
        proxy_symbol=None,
        source="akshare",
        metadata={"provider": "rank"},
    )

    cache.upsert_funds([fund], as_of="2026-06-22", ttl_days=3)
    cached = cache.load_funds(as_of="2026-06-22")

    assert len(cached) == 1
    assert cached[0].code == "510300"
    assert cached[0].source == "cache:akshare"
    assert cached[0].returns == {"1m": 3.2, "3m": 7.8}
    assert cached[0].metadata["provider"] == "rank"
    assert cached[0].metadata["cache_source"] == "akshare"
    assert cached[0].metadata["stale"] is False


def test_cache_filters_expired_records_unless_stale_allowed(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    fund = FundRecord(
        code="000311",
        name="华夏沪深300ETF联接A",
        category="ETF联接",
        nav=1.42,
        nav_date="2026-06-21",
        source="akshare",
    )
    now = datetime(2026, 6, 22, tzinfo=timezone.utc)

    cache.upsert_funds([fund], as_of="2026-06-22", ttl_days=1, now=now - timedelta(days=3))

    assert cache.load_funds(as_of="2026-06-22", now=now) == []

    stale = cache.load_funds(as_of="2026-06-22", allow_stale=True, now=now)

    assert len(stale) == 1
    assert stale[0].metadata["stale"] is True
    assert stale[0].metadata["expires_at"] < now.isoformat()


def test_cache_round_trips_fund_details(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    detail = FundDetail(
        code="510300",
        name="沪深300ETF",
        fund_type="ETF",
        fund_company="华泰柏瑞基金",
        fund_manager="张三",
        inception_date="2012-05-04",
        scale=460.5,
        rating="5",
        source="tiantian",
        as_of="2026-06-23",
    )

    cache.upsert_fund_details([detail], as_of="2026-06-23", ttl_days=3)
    cached = cache.load_fund_details(code="510300", as_of="2026-06-23")

    assert len(cached) == 1
    assert cached[0].code == "510300"
    assert cached[0].source == "cache:tiantian"
    assert cached[0].fund_company == "华泰柏瑞基金"
    assert cached[0].metadata["stale"] is False


def test_cache_round_trips_fund_nav_points(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    navs = [
        FundNavPoint(
            code="510300",
            date="2026-06-21",
            unit_nav=5.01,
            accumulated_nav=5.01,
            daily_return=0.12,
            source="tiantian",
        )
    ]

    cache.upsert_nav_points(navs, as_of="2026-06-23", ttl_days=3)
    cached = cache.load_nav_points(code="510300")

    assert len(cached) == 1
    assert cached[0].source == "cache:tiantian"
    assert cached[0].unit_nav == 5.01
    assert cached[0].accumulated_nav == 5.01
    assert cached[0].daily_return == 0.12
    assert cached[0].metadata["cache_as_of"] == "2026-06-23"


def test_tiantian_cache_stale_metadata_is_available_for_fallback(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    old_now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    current_now = datetime(2026, 6, 23, tzinfo=timezone.utc)
    cache.upsert_fund_details(
        [FundDetail(code="510300", name="沪深300ETF", source="tiantian")],
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

    details = cache.load_fund_details(code="510300", as_of="2026-06-23", allow_stale=True, now=current_now)
    navs = cache.load_nav_points(code="510300", allow_stale=True, now=current_now)

    assert details[0].source == "cache:tiantian"
    assert navs[0].source == "cache:tiantian"
    assert details[0].metadata["stale"] is True
    assert navs[0].metadata["stale"] is True
