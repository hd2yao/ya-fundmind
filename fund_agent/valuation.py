from __future__ import annotations

from .models import FundRecord, ValuationResult


def classify_valuation(fund: FundRecord) -> str:
    category = fund.category.lower()
    name = fund.name.lower()
    if fund.exchange_traded and fund.price is not None:
        return "etf_price"
    if fund.proxy_symbol or "qdii" in category or "纳斯达克" in fund.name or "标普" in fund.name:
        return "qdii_proxy"
    if fund.target_etf or "联接" in fund.name:
        return "feeder"
    if fund.nav is not None:
        if any(token in category or token in name for token in ("指数", "etf", "lof")):
            return "index_based"
        return "nav_only"
    return "unsupported"


def estimate_value(fund: FundRecord) -> ValuationResult:
    method = classify_valuation(fund)
    if method == "etf_price":
        return ValuationResult(
            fund=fund,
            method=method,
            estimated_value=fund.price,
            confidence="High",
            notes=("场内产品使用交易价格；需另行关注折溢价。",),
        )
    if method == "feeder":
        note = f"ETF 联接基金，目标 ETF: {fund.target_etf or '待确认'}。"
        return ValuationResult(
            fund=fund,
            method=method,
            estimated_value=fund.nav,
            confidence="Medium" if fund.target_etf else "Needs checking",
            notes=(note, "第一版以最新净值为估值基准，目标 ETF 用于后续盘中估算。"),
        )
    if method == "qdii_proxy":
        note = f"QDII/跨境产品，代理指数或 ETF: {fund.proxy_symbol or '待确认'}。"
        return ValuationResult(
            fund=fund,
            method=method,
            estimated_value=fund.nav,
            confidence="Medium" if fund.proxy_symbol else "Needs checking",
            notes=(
                note,
                fund.proxy_symbol or "proxy_missing",
                "跨境产品存在时区、汇率和申赎限制，盘中估值仅作参考。",
            ),
        )
    if method == "index_based":
        return ValuationResult(
            fund=fund,
            method=method,
            estimated_value=fund.nav,
            confidence="Medium",
            notes=("指数/LOF 产品以最新净值为基准；盘中指数映射待补全。",),
        )
    if method == "nav_only":
        return ValuationResult(
            fund=fund,
            method=method,
            estimated_value=fund.nav,
            confidence="Low",
            notes=("开放式基金仅使用最新净值，无法代表盘中实时可交易价格。",),
        )
    return ValuationResult(
        fund=fund,
        method="unsupported",
        estimated_value=None,
        confidence="Needs checking",
        notes=("缺少净值、价格或代理标的，暂不支持估值。",),
    )
