from fund_agent.market_intelligence import (
    MarketFundRecord,
    classify_market_fund,
    load_market_theme_rules,
)


def test_market_theme_rule_classification_supports_multiple_themes():
    rules = load_market_theme_rules("configs/market_themes.yaml")
    record = MarketFundRecord(
        code="000311",
        name="华夏沪深300ETF联接A",
        fund_type="ETF联接",
        source="fixture",
        as_of="2026-06-23",
        exchange_traded=False,
        metadata={},
    )

    classification = classify_market_fund(record, rules)

    assert "沪深300" in classification.themes
    assert "ETF联接" in classification.themes
    assert classification.primary_theme == "沪深300"
    assert classification.confidence > 0


def test_unknown_theme_is_safe_when_no_rule_matches():
    rules = load_market_theme_rules("configs/market_themes.yaml")
    record = MarketFundRecord(
        code="999999",
        name="普通混合基金A",
        fund_type="混合型",
        source="fixture",
        as_of="2026-06-23",
        metadata={},
    )

    classification = classify_market_fund(record, rules)

    assert classification.themes == ("unknown",)
    assert classification.primary_theme == "unknown"
    assert classification.confidence == 0.0
