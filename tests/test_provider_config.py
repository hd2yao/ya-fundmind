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
  trace_retention_days: 14
  max_trace_files: 20
policy:
  fail_on_degraded: true
  fail_on_critical_provider_warning: true
tiantian:
  timeout_seconds: 9
  retry_count: 1
  retry_backoff_seconds: 0.25
  trace_retention_days: 7
  max_trace_files: 10
""",
        encoding="utf-8",
    )

    provider_config = load_provider_config(config)
    settings = provider_config.akshare
    tiantian = provider_config.tiantian

    assert settings.timeout_seconds == 12
    assert settings.retry_count == 2
    assert settings.retry_backoff_seconds == 0.5
    assert settings.verbose is True
    assert settings.trace_retention_days == 14
    assert settings.max_trace_files == 20
    assert tiantian.timeout_seconds == 9
    assert tiantian.retry_count == 1
    assert tiantian.retry_backoff_seconds == 0.25
    assert tiantian.trace_retention_days == 7
    assert tiantian.max_trace_files == 10
    assert provider_config.policy.fail_on_degraded is True
    assert provider_config.policy.fail_on_critical_provider_warning is True


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
