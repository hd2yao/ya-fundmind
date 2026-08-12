from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent.cache import FundCache
from fund_agent.fund_profile import FundProfileService
from fund_agent.models import (
    FundCatalogEntry,
    FundFee,
    FundProfile,
    FundProfileBundle,
    FundTradingRule,
)
from fund_agent.web_api import create_web_app


def _write_market(output_dir: Path, code: str = "021511") -> None:
    path = output_dir / "market" / "market_intelligence_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "as_of": "2026-07-28",
                "source": "akshare",
                "records": [
                    {
                        "code": code,
                        "name": "示例混合A",
                        "fund_type": "混合型",
                        "source": "akshare",
                        "as_of": "2026-07-28",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _bundle() -> FundProfileBundle:
    return FundProfileBundle(
        code="021511",
        catalog=FundCatalogEntry(
            code="021511",
            name="示例混合A",
            fund_type="混合型",
            source="cache:akshare",
            as_of="2026-07-28",
            metadata={"endpoint": "fund_name_em"},
        ),
        profile=FundProfile(
            code="021511",
            name="示例混合A",
            full_name="示例混合型证券投资基金A",
            fund_type="混合型",
            fund_company="示例基金",
            custodian="示例银行",
            fund_manager="甲、乙",
            inception_date="2024-07-01",
            asset_scale=5.6,
            asset_scale_unit="亿元",
            benchmark="示例比较基准",
            source="cache:akshare",
            as_of="2026-07-28",
            stale=True,
            metadata={"endpoint": "fund_overview_em"},
        ),
        trading_rule=FundTradingRule(
            code="021511",
            purchase_status="开放申购",
            redemption_status="开放赎回",
            next_open_date="2026-07-29",
            minimum_purchase_amount="10元",
            source="cache:akshare",
            as_of="2026-07-28",
            stale=False,
            metadata={"endpoint": "fund_fee_em"},
        ),
        fees=(
            FundFee(
                code="021511",
                fee_type="申购费率（前端）",
                condition="小于100万元",
                channel="银行卡购买",
                original_rate="1.20%",
                discounted_rate="0.12%",
                source="cache:akshare",
                as_of="2026-07-28",
                metadata={"endpoint": "fund_fee_em"},
            ),
        ),
        data_status="limited",
        profile_status="limited",
        trading_status="updated",
        fee_status="updated",
        warnings=({"code": "stale_cache", "message": "internal"},),
    )


class StubProfileService:
    def __init__(self, bundle: FundProfileBundle):
        self.bundle = bundle
        self.calls: list[str] = []

    def get_profile(self, code: str, **_kwargs):
        self.calls.append(code)
        return self.bundle


def _assert_no_product_diagnostics(value) -> None:
    forbidden = {
        "source",
        "updated_at",
        "expires_at",
        "stale",
        "fallback_used",
        "fallback_reason",
        "data_quality_grade",
        "warnings",
        "schema_version",
        "metadata",
        "endpoint",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for child in value.values():
            _assert_no_product_diagnostics(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_product_diagnostics(child)


def test_product_profile_route_is_safe_partial_and_not_shadowed(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    service = StubProfileService(_bundle())
    client = TestClient(
        create_web_app(output_dir=output_dir, fund_profile_service=service)
    )

    response = client.get("/api/product/funds/021511/profile")

    assert response.status_code == 200
    assert service.calls == ["021511"]
    payload = response.json()
    assert payload["fund"] == {
        "code": "021511",
        "name": "示例混合A",
        "fund_type": "混合型",
    }
    assert payload["profile"]["custodian"] == "示例银行"
    assert payload["trading_rule"]["next_open_date"] == "2026-07-29"
    assert payload["fees"][0]["discounted_rate"] == "0.12%"
    assert payload["data_status"]["state"] == "limited"
    assert payload["component_status"]["trading_rule"]["state"] == "updated"
    _assert_no_product_diagnostics(payload)


def test_diagnostics_profile_route_keeps_provenance_for_local_tools(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    service = StubProfileService(_bundle())
    client = TestClient(
        create_web_app(output_dir=output_dir, fund_profile_service=service)
    )

    response = client.get("/api/funds/021511/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["profile"]["source"] == "cache:akshare"
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False


class CodeScopedProvider:
    def __init__(self):
        self.calls: list[str] = []

    def fetch_fund_profile(self, code, **_kwargs):
        self.calls.append("profile")
        return FundProfile(code=code, name="目录基金", source="akshare")

    def fetch_fund_trading_rule(self, code, **_kwargs):
        self.calls.append("rule")
        return FundTradingRule(code=code, purchase_status="开放申购", source="akshare")

    def fetch_fund_fees(self, code, **_kwargs):
        self.calls.append("fees")
        return [FundFee(code=code, fee_type="申购费率", original_rate="1.20%", source="akshare")]

    def fetch_fund_catalog(self, *_args, **_kwargs):
        raise AssertionError("detail route must not call the full catalog endpoint")

    def fetch_purchase_statuses(self, *_args, **_kwargs):
        raise AssertionError("detail route must not call fund_purchase_em")


class CatalogHistoryService:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def get_history(self, code, *, window):
        self.calls.append((code, window))
        return {
            "code": code,
            "range": window,
            "point_count": 1,
            "points": [{"date": "2026-07-28", "unit_nav": 1.2}],
            "as_of": "2026-07-28",
            "stale": False,
            "fallback_used": False,
            "data_quality_grade": "normal",
        }


def test_catalog_only_code_opens_detail_and_profile_without_full_endpoint_calls(tmp_path):
    now = datetime.now(timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.replace_fund_catalog_snapshot(
        [
            FundCatalogEntry(
                code="021511",
                name="目录基金",
                fund_type="混合型",
                source="akshare",
            )
        ],
        snapshot_id="catalog-v1",
        as_of=now.date().isoformat(),
        now=now,
    )
    provider = CodeScopedProvider()
    service = FundProfileService(cache=cache, provider=provider)
    history_service = CatalogHistoryService()
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            fund_profile_service=service,
            fund_history_service=history_service,
        )
    )

    detail = client.get("/api/product/funds/021511")
    profile = client.get("/api/product/funds/021511/profile")
    history = client.get("/api/product/funds/021511/history")

    assert detail.status_code == 200
    assert detail.json()["fund"]["name"] == "目录基金"
    assert profile.status_code == 200
    assert history.status_code == 200
    assert history_service.calls == [("021511", "6m")]
    assert provider.calls == ["profile", "rule", "fees"]


def test_product_profile_rejects_invalid_or_unknown_code(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    service = StubProfileService(_bundle())
    client = TestClient(
        create_web_app(output_dir=output_dir, fund_profile_service=service)
    )

    invalid = client.get("/api/product/funds/not-a-code/profile")
    missing = client.get("/api/product/funds/999999/profile")

    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert service.calls == []
