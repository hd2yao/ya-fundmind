from pathlib import Path


def test_daily_ops_script_keeps_market_intelligence_disabled_by_default():
    text = Path("scripts/run_daily_ops.sh").read_text(encoding="utf-8")

    assert 'ENABLE_MARKET_INTELLIGENCE="${ENABLE_MARKET_INTELLIGENCE:-false}"' in text
    assert "market-scan" in text
    assert "market-trend" in text
    assert "watchlist-detail" in text
    assert "portfolio-analysis" in text
    assert "collect-news-evidence" in text
    assert "market intelligence warning" in text
    assert "market trend warning" in text
    assert "watchlist detail warning" in text
    assert "portfolio analysis warning" in text
    assert "news evidence warning" in text
    assert "--provider \"${PROVIDER}\"" in text
    assert "--watchlist-file \"${WATCHLIST_FILE}\"" in text
    assert "REFRESH_DASHBOARD" in text
    assert 'RUN_TRIGGER="${RUN_TRIGGER:-daily_ops}"' in text
    assert "export RUN_TRIGGER" in text
