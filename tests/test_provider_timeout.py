import time

import pytest

from fund_agent.providers import ProviderCallTimeout, _call_with_timeout


def test_akshare_call_timeout_returns_within_wall_clock_budget() -> None:
    def slow_call():
        time.sleep(1.0)
        return "late"

    started = time.perf_counter()
    with pytest.raises(ProviderCallTimeout, match="timed out after 0.05 seconds"):
        _call_with_timeout(
            slow_call,
            timeout_seconds=0.05,
            verbose=False,
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3


def test_akshare_call_timeout_preserves_successful_calls() -> None:
    result = _call_with_timeout(
        lambda: "ok",
        timeout_seconds=0.5,
        verbose=False,
    )

    assert result == "ok"
