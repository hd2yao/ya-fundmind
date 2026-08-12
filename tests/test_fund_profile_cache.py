from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from fund_agent.cache import FundCache
from fund_agent.models import (
    FundCatalogEntry,
    FundDetail,
    FundFee,
    FundProfile,
    FundRecord,
    FundTradingRule,
)


M2_TABLES = {
    "fund_catalog_snapshots",
    "fund_catalog_entries",
    "fund_purchase_snapshots",
    "fund_purchase_statuses",
    "fund_profiles",
    "fund_trading_rules",
    "fund_fees",
}


def _raw_table(path, table: str):
    with sqlite3.connect(path) as conn:
        schema = conn.execute(f"PRAGMA table_info({table})").fetchall()
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    return schema, rows


def test_profile_schema_is_additive_and_legacy_tables_stay_byte_for_byte_stable(tmp_path):
    path = tmp_path / "funds.sqlite"
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache = FundCache(path)
    cache.upsert_funds(
        [
            FundRecord(
                code="021511",
                name="示例混合A",
                category="混合型",
                nav=1.25,
                nav_date="2026-07-28",
                source="akshare",
            )
        ],
        as_of="2026-07-28",
        now=now,
    )
    cache.upsert_fund_details(
        [FundDetail(code="021511", name="旧详情", source="tiantian")],
        as_of="2026-07-28",
        now=now,
    )
    legacy_before = {
        table: _raw_table(path, table)
        for table in ("fund_basics", "fund_details")
    }

    cache.replace_fund_catalog_snapshot(
        [
            FundCatalogEntry(
                code="021511",
                name="示例混合A",
                fund_type="混合型",
                catalog_sources=("fund_name_em",),
                source="akshare",
            )
        ],
        snapshot_id="catalog-20260728",
        as_of="2026-07-28",
        now=now,
    )
    cache.replace_purchase_snapshot(
        [
            FundTradingRule(
                code="021511",
                purchase_status="开放申购",
                redemption_status="开放赎回",
                source="akshare",
            )
        ],
        snapshot_id="purchase-20260728",
        as_of="2026-07-28",
        now=now,
    )
    cache.upsert_fund_profiles(
        [FundProfile(code="021511", name="示例混合A", source="akshare")],
        as_of="2026-07-28",
        now=now,
    )

    assert M2_TABLES <= cache.table_names()
    assert {
        table: _raw_table(path, table)
        for table in ("fund_basics", "fund_details")
    } == legacy_before


def test_catalog_snapshot_only_switches_active_version_after_validation(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache.replace_fund_catalog_snapshot(
        [FundCatalogEntry(code="021511", name="旧目录", source="akshare")],
        snapshot_id="catalog-v1",
        as_of="2026-07-27",
        minimum_entry_count=1,
        now=now,
    )

    with pytest.raises(ValueError, match="minimum entry count"):
        cache.replace_fund_catalog_snapshot(
            [],
            snapshot_id="catalog-v2-bad",
            as_of="2026-07-28",
            minimum_entry_count=1,
            now=now,
        )

    with pytest.raises(ValueError, match="minimum mapped ratio"):
        cache.replace_fund_catalog_snapshot(
            [FundCatalogEntry(code="021511", name="不完整目录", source="akshare")],
            snapshot_id="catalog-v2-incomplete",
            as_of="2026-07-28",
            raw_entry_count=10,
            minimum_mapped_ratio=0.8,
            now=now,
        )

    assert [item.name for item in cache.load_catalog_entries(now=now)] == ["旧目录"]

    cache.replace_fund_catalog_snapshot(
        [FundCatalogEntry(code="021511", name="新目录", source="akshare")],
        snapshot_id="catalog-v2",
        as_of="2026-07-28",
        minimum_entry_count=1,
        now=now,
    )

    assert [item.name for item in cache.load_catalog_entries(now=now)] == ["新目录"]


def test_purchase_snapshot_validation_failure_keeps_previous_active_snapshot(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache.replace_purchase_snapshot(
        [FundTradingRule(code="021511", purchase_status="开放申购", source="akshare")],
        snapshot_id="purchase-v1",
        as_of="2026-07-27",
        now=now,
    )

    with pytest.raises(ValueError, match="minimum mapped ratio"):
        cache.replace_purchase_snapshot(
            [FundTradingRule(code="021511", purchase_status="暂停申购", source="akshare")],
            snapshot_id="purchase-v2-incomplete",
            as_of="2026-07-28",
            raw_entry_count=20,
            minimum_mapped_ratio=0.9,
            now=now,
        )

    active = cache.load_purchase_statuses(code="021511", now=now)
    assert active[0].purchase_status == "开放申购"


def test_purchase_snapshot_and_profile_components_round_trip_with_stale_semantics(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    rule = FundTradingRule(
        code="021511",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        next_open_date="2026-07-29",
        source="akshare",
    )
    profile = FundProfile(
        code="021511",
        name="示例混合A",
        asset_scale=5.6,
        asset_scale_unit="亿元",
        source="akshare",
    )
    fees = [
        FundFee(
            code="021511",
            fee_type="申购费率（前端）",
            condition="小于100万元",
            channel="银行卡购买",
            original_rate="1.20%",
            discounted_rate="0.12%",
            source="akshare",
        )
    ]
    cache.replace_purchase_snapshot(
        [rule],
        snapshot_id="purchase-v1",
        as_of="2026-07-28",
        ttl_days=1,
        now=now,
    )
    cache.upsert_fund_profiles([profile], as_of="2026-07-28", ttl_days=1, now=now)
    cache.upsert_fund_trading_rules([rule], as_of="2026-07-28", ttl_days=1, now=now)
    cache.replace_fund_fees("021511", fees, as_of="2026-07-28", ttl_days=1, now=now)

    assert cache.load_purchase_statuses(code="021511", now=now)[0].source == "cache:akshare"
    assert cache.load_fund_profiles(code="021511", now=now)[0].asset_scale == 5.6
    assert cache.load_fund_trading_rules(code="021511", now=now)[0].next_open_date == "2026-07-29"
    assert cache.load_fund_fees(code="021511", now=now)[0].discounted_rate == "0.12%"

    future = now + timedelta(days=2)
    assert cache.load_fund_profiles(code="021511", now=future) == []
    stale = cache.load_fund_profiles(code="021511", allow_stale=True, now=future)
    assert stale[0].stale is True
    assert stale[0].source == "cache:akshare"
