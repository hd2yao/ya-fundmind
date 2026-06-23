from fund_agent.config import load_provider_config
from fund_agent.providers import AkshareProvider


def test_provider_config_loads_akshare_defaults(tmp_path):
    config = tmp_path / "providers.yaml"
    config.write_text(
        """
akshare:
  timeout_seconds: 12
  retry_count: 2
  retry_backoff_seconds: 0.5
  verbose: true
""",
        encoding="utf-8",
    )

    settings = load_provider_config(config).akshare

    assert settings.timeout_seconds == 12
    assert settings.retry_count == 2
    assert settings.retry_backoff_seconds == 0.5
    assert settings.verbose is True


def test_akshare_provider_uses_retry_config():
    class FlakyAkshare:
        __version__ = "9.9.9"

        def __init__(self):
            self.calls = 0

        def fund_open_fund_rank_em(self, symbol):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary")
            return FakeDataFrame([(0, {"基金代码": "000311", "基金简称": "沪深300增强A"})])

    class FakeDataFrame:
        def __init__(self, rows):
            self._rows = rows

        def iterrows(self):
            return iter(self._rows)

    ak = FlakyAkshare()
    provider = AkshareProvider(
        ak_module=ak,
        retry_count=1,
        retry_backoff_seconds=0,
    )

    funds = provider.fetch_funds(as_of="2026-06-23")

    assert funds
    assert ak.calls == 2
    assert provider.last_health.endpoints[0].attempts == 2
