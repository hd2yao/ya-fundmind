from fund_agent.cache import FundCache
from fund_agent.models import FundDetail, FundNavPoint, ProviderEndpointTrace
from fund_agent.providers import ProviderUnavailable, TiantianFundProvider, TiantianProviderError


class FakeTiantianClient:
    __version__ = "0.1-test"

    def fund_detail(self, code):
        return {
            "code": f"SH{code}",
            "name": "沪深300ETF",
            "fund_type": "ETF",
            "fund_company": "华泰柏瑞基金",
            "fund_manager": "张三",
            "inception_date": "2012-05-04",
            "scale": "460.5",
            "rating": "5",
        }

    def nav_history(self, code, start_date=None, end_date=None):
        return [
            {"date": "2026-06-21", "unit_nav": "5.01", "accumulated_nav": "5.01", "daily_return": "0.12%"},
            {"date": "", "unit_nav": "--"},
            {"date": "2026-06-22", "unit_nav": "5.02", "accumulated_nav": "5.02", "daily_return": "0.20%"},
        ]


class MissingFieldClient:
    def fund_detail(self, code):
        return {"code": code, "name": "沪深300ETF"}

    def nav_history(self, code, start_date=None, end_date=None):
        return []


class PaginatedTraceClient(FakeTiantianClient):
    def nav_history(self, code, start_date=None, end_date=None):
        self.last_endpoint_traces = (
            ProviderEndpointTrace(
                endpoint="tiantian_nav_history",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                attempts=2,
                success=True,
                timeout_seconds=5.0,
                live_row_count=2,
            ),
            ProviderEndpointTrace(
                endpoint="tiantian_nav_history",
                started_at="2026-06-23T00:00:01+00:00",
                finished_at="2026-06-23T00:00:02+00:00",
                duration_ms=1000,
                attempts=1,
                success=True,
                timeout_seconds=5.0,
                live_row_count=1,
            ),
        )
        return super().nav_history(code, start_date=start_date, end_date=end_date)


class InvalidResponseClient:
    def fund_detail(self, code):
        raise TiantianProviderError("invalid_response", "bad json")

    def nav_history(self, code, start_date=None, end_date=None):
        raise TiantianProviderError("invalid_response", "bad json")


def test_tiantian_provider_maps_fund_detail_successfully(tmp_path):
    provider = TiantianFundProvider(client=FakeTiantianClient(), cache=FundCache(tmp_path / "funds.sqlite"))

    detail = provider.fetch_fund_detail("SH510300", as_of="2026-06-23")

    assert isinstance(detail, FundDetail)
    assert detail.code == "510300"
    assert detail.name == "沪深300ETF"
    assert detail.fund_company == "华泰柏瑞基金"
    assert detail.fund_manager == "张三"
    assert detail.scale == 460.5
    assert detail.rating == "5"
    assert detail.source == "tiantian"
    assert detail.metadata["provider"] == "tiantian"
    assert detail.metadata["updated_at"]
    assert detail.metadata["expires_at"]


def test_tiantian_provider_maps_nav_history_and_skips_bad_rows(tmp_path):
    provider = TiantianFundProvider(client=FakeTiantianClient(), cache=FundCache(tmp_path / "funds.sqlite"))

    navs = provider.fetch_nav_history("510300", start_date="2026-06-01", end_date="2026-06-23")

    assert [item.date for item in navs] == ["2026-06-21", "2026-06-22"]
    assert all(isinstance(item, FundNavPoint) for item in navs)
    assert navs[0].unit_nav == 5.01
    assert navs[0].daily_return == 0.12
    assert navs[0].metadata["updated_at"]
    assert navs[0].metadata["expires_at"]
    assert provider.last_health is not None
    assert provider.last_health.provider == "tiantian"
    assert provider.last_health.live_row_count == 3
    assert provider.last_health.mapped_row_count == 2
    assert provider.last_health.skipped_row_count == 1
    assert any(warning.code == "skipped_rows" for warning in provider.last_health.warnings)


def test_tiantian_detail_missing_fields_degrades_safely(tmp_path):
    provider = TiantianFundProvider(client=MissingFieldClient(), cache=FundCache(tmp_path / "funds.sqlite"))

    detail = provider.fetch_fund_detail("510300", as_of="2026-06-23")

    assert detail.code == "510300"
    assert detail.name == "沪深300ETF"
    assert detail.fund_type is None
    assert detail.fund_company is None
    assert detail.scale is None
    assert provider.last_health is not None
    warning_codes = {warning.code for warning in provider.last_health.warnings}
    assert "detail_missing_fund_company" in warning_codes
    assert "detail_missing_fund_manager" in warning_codes
    assert "detail_missing_scale" in warning_codes


def test_tiantian_provider_preserves_paginated_endpoint_traces(tmp_path):
    provider = TiantianFundProvider(client=PaginatedTraceClient(), cache=FundCache(tmp_path / "funds.sqlite"))

    provider.fetch_nav_history("510300", as_of="2026-06-23")

    assert provider.last_health is not None
    assert len(provider.last_health.endpoints) == 2
    assert provider.last_health.endpoints[0].attempts == 2
    assert provider.last_health.endpoints[0].timeout_seconds == 5.0


def test_tiantian_provider_uses_classified_error_warning(tmp_path):
    provider = TiantianFundProvider(client=InvalidResponseClient(), cache=FundCache(tmp_path / "funds.sqlite"))

    try:
        provider.fetch_nav_history("510300", as_of="2026-06-23")
    except ProviderUnavailable as exc:
        assert "invalid_response" in str(exc)
    else:
        raise AssertionError("expected ProviderUnavailable")

    assert provider.last_health is not None
    assert provider.last_health.fallback_used is True
    assert provider.last_health.warnings[0].code == "invalid_response"


def test_tiantian_provider_without_client_is_unavailable(monkeypatch):
    monkeypatch.delenv("TIANTIAN_API_BASE_URL", raising=False)
    provider = TiantianFundProvider()

    try:
        provider.fetch_fund_detail("510300")
    except ProviderUnavailable as exc:
        assert "TiantianFundProvider" in str(exc)
    else:
        raise AssertionError("expected ProviderUnavailable")
    assert provider.last_health is not None
    assert provider.last_health.warnings[0].code == "config_missing"
