from __future__ import annotations

from fund_agent.providers import (
    AkshareProvider,
    _fund_fees_from_akshare_rows,
    _fund_profile_from_akshare_row,
    _merge_trading_rule_rows,
    _purchase_rules_from_rows,
)
from fund_agent.cache import FundCache


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class BadRow:
    def get(self, key):
        raise ValueError(f"bad field: {key}")


def test_fund_overview_mapper_preserves_profile_semantics() -> None:
    profile = _fund_profile_from_akshare_row(
        {
            "基金代码": "SH021511",
            "基金简称": "华夏产业升级混合A",
            "基金全称": "华夏产业升级混合型证券投资基金A",
            "基金类型": "混合型-偏股",
            "发行日期": "2024-06-10",
            "成立日期/规模": "2024-07-01 / 3.20亿份",
            "资产规模": "5.60亿元（截至：2026-06-30）",
            "基金管理人": "华夏基金管理有限公司",
            "基金托管人": "示例银行",
            "基金经理人": "示例经理",
            "业绩比较基准": "沪深300指数收益率×80%+中债指数收益率×20%",
            "跟踪标的": "该基金无跟踪标的",
        }
    )

    assert profile.code == "021511"
    assert profile.name == "华夏产业升级混合A"
    assert profile.full_name == "华夏产业升级混合型证券投资基金A"
    assert profile.fund_type == "混合型-偏股"
    assert profile.issue_date == "2024-06-10"
    assert profile.inception_date == "2024-07-01"
    assert profile.asset_scale == 5.6
    assert profile.asset_scale_unit == "亿元"
    assert profile.share_scale == 3.2
    assert profile.share_scale_unit == "亿份"
    assert profile.fund_company == "华夏基金管理有限公司"
    assert profile.custodian == "示例银行"
    assert profile.fund_manager == "示例经理"
    assert profile.tracking_target is None
    assert profile.source == "akshare"


def test_fund_overview_mapper_uses_requested_code_and_aliases() -> None:
    profile = _fund_profile_from_akshare_row(
        {
            "基金名称": "示例ETF联接A",
            "类型": "指数型-股票",
            "基金成立日": "2023-01-02",
            "管理人": "示例基金",
            "基金经理": "甲、乙",
            "跟踪标的名称": "沪深300指数",
        },
        code=" 021580.OF ",
    )

    assert profile.code == "021580"
    assert profile.name == "示例ETF联接A"
    assert profile.inception_date == "2023-01-02"
    assert profile.fund_company == "示例基金"
    assert profile.fund_manager == "甲、乙"
    assert profile.tracking_target == "沪深300指数"


def test_fund_overview_mapper_rejects_missing_or_invalid_code() -> None:
    for code in (None, "", "123", "ABCDEF"):
        try:
            _fund_profile_from_akshare_row({"基金名称": "无效资料"}, code=code)
        except ValueError as exc:
            assert "six-digit fund code" in str(exc)
        else:  # pragma: no cover - makes the failure message explicit
            raise AssertionError(f"invalid code was accepted: {code!r}")


def test_fee_mapper_expands_channels_and_keeps_fixed_amount_text() -> None:
    result = _fund_fees_from_akshare_rows(
        FakeDataFrame(
            [
                (
                    0,
                    {
                        "适用金额": "小于100万元",
                        "适用期限": "-",
                        "原费率": "1.20%",
                        "天天基金优惠费率-银行卡购买": "0.12%",
                        "天天基金优惠费率-活期宝购买": "0.10%",
                    },
                ),
                (
                    1,
                    {
                        "适用金额": "1000万元以上",
                        "费率": "每笔1000元",
                    },
                ),
            ]
        ),
        code="021511",
        indicator="申购费率（前端）",
    )

    assert result.live_row_count == 2
    assert result.skipped_row_count == 0
    assert len(result.fees) == 3
    assert [fee.channel for fee in result.fees[:2]] == ["银行卡购买", "活期宝购买"]
    assert result.fees[0].original_rate == "1.20%"
    assert result.fees[0].discounted_rate == "0.12%"
    assert result.fees[1].discounted_rate == "0.10%"
    assert result.fees[2].original_rate == "每笔1000元"
    assert result.fees[2].discounted_rate is None
    assert result.fees[2].condition == "1000万元以上"


def test_fee_mapper_skips_empty_and_malformed_rows() -> None:
    result = _fund_fees_from_akshare_rows(
        FakeDataFrame(
            [
                (0, {"适用金额": "", "费率": ""}),
                (1, BadRow()),
            ]
        ),
        code="021511",
        indicator="赎回费率",
    )

    assert result.live_row_count == 2
    assert result.fees == ()
    assert result.skipped_row_count == 2
    assert all(warning.code == "skipped_rows" for warning in result.warnings)


def test_fee_mapper_accepts_runtime_redemption_rate_column() -> None:
    result = _fund_fees_from_akshare_rows(
        FakeDataFrame(
            [
                (0, {"适用期限": "大于等于1天，小于等于6天", "赎回费率": "1.50%"}),
                (1, {"适用期限": "大于等于30天", "赎回费率": "0.00%"}),
            ]
        ),
        code="021511",
        indicator="赎回费率",
    )

    assert [(fee.period, fee.original_rate) for fee in result.fees] == [
        ("大于等于1天，小于等于6天", "1.50%"),
        ("大于等于30天", "0.00%"),
    ]
    assert result.skipped_row_count == 0


def test_fee_mapper_expands_runtime_operation_fee_pairs() -> None:
    result = _fund_fees_from_akshare_rows(
        FakeDataFrame(
            [
                (
                    0,
                    {
                        "0": "管理费率",
                        "1": "1.20%（每年）",
                        "2": "托管费率",
                        "3": "0.20%（每年）",
                        "4": "销售服务费率",
                        "5": "0.30%（每年）",
                    },
                )
            ]
        ),
        code="021511",
        indicator="运作费用",
    )

    assert [(fee.fee_type, fee.original_rate) for fee in result.fees] == [
        ("管理费率", "1.20%（每年）"),
        ("托管费率", "0.20%（每年）"),
        ("销售服务费率", "0.30%（每年）"),
    ]
    assert result.skipped_row_count == 0


def test_trading_rule_mapper_accepts_runtime_label_value_pairs() -> None:
    values = {
        "purchase_status": None,
        "redemption_status": None,
        "next_open_date": None,
        "minimum_purchase_amount": None,
        "daily_purchase_limit": None,
        "confirmation_rule": None,
    }

    first_counts = _merge_trading_rule_rows(
        FakeDataFrame(
            [
                (
                    0,
                    {
                        "0": "申购状态",
                        "1": "开放申购",
                        "2": "赎回状态",
                        "3": "开放赎回",
                        "4": "定投状态",
                        "5": "支持",
                    },
                )
            ]
        ),
        values,
        indicator="交易状态",
    )
    _merge_trading_rule_rows(
        FakeDataFrame(
            [
                (
                    0,
                    {
                        "0": "申购起点",
                        "1": "10.00元",
                        "2": "定投起点",
                        "3": "10.00元",
                        "4": "日累计申购限额",
                        "5": "无限额",
                    },
                )
            ]
        ),
        values,
        indicator="申购与赎回金额",
    )
    _merge_trading_rule_rows(
        FakeDataFrame(
            [(0, {"0": "买入确认日", "1": "T+1", "2": "卖出确认日", "3": "T+1"})]
        ),
        values,
        indicator="交易确认日",
    )

    assert first_counts[:3] == (1, 1, 0)
    assert values == {
        "purchase_status": "开放申购",
        "redemption_status": "开放赎回",
        "next_open_date": None,
        "minimum_purchase_amount": "10.00元",
        "daily_purchase_limit": "无限额",
        "confirmation_rule": "买入确认日 T+1；卖出确认日 T+1",
    }


def test_purchase_snapshot_treats_nat_as_missing_date() -> None:
    result = _purchase_rules_from_rows(
        FakeDataFrame(
            [
                (
                    0,
                    {
                        "基金代码": "021511",
                        "基金简称": "示例混合C",
                        "申购状态": "开放申购",
                        "赎回状态": "开放赎回",
                        "下一开放日": "NaT",
                        "购买起点": 0,
                        "日累计限定金额": 0,
                        "手续费": 0,
                    },
                )
            ]
        ),
        endpoint="fund_purchase_em",
    )

    assert result.rules[0].next_open_date is None
    assert result.rules[0].minimum_purchase_amount == "0"
    assert result.rules[0].daily_purchase_limit == "0"
    assert result.rules[0].metadata["fee_text"] == "0"


class ProfileAkshare:
    __version__ = "9.9.9"

    def __init__(self):
        self.calls = []

    def fund_name_em(self):
        self.calls.append(("fund_name_em", {}))
        return FakeDataFrame(
            [
                (0, {"基金代码": "021511", "基金简称": "示例混合A", "基金类型": "混合型"}),
                (1, {"基金代码": "021580", "基金简称": "示例ETF联接A", "基金类型": "指数型"}),
                (2, {"基金代码": "", "基金简称": "坏行"}),
            ]
        )

    def fund_open_fund_rank_em(self, *, symbol):
        self.calls.append(("fund_open_fund_rank_em", {"symbol": symbol}))
        return FakeDataFrame(
            [
                (0, {"基金代码": "021511", "基金简称": "示例混合A", "基金类型": "混合型-偏股"}),
                (1, {"基金代码": "000311", "基金简称": "示例指数联接A", "基金类型": "指数型"}),
            ]
        )

    def fund_etf_spot_em(self):
        self.calls.append(("fund_etf_spot_em", {}))
        return FakeDataFrame([(0, {"代码": "510300", "名称": "沪深300ETF"})])

    def fund_purchase_em(self):
        self.calls.append(("fund_purchase_em", {}))
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "基金代码": "021511",
                        "基金简称": "示例混合A",
                        "申购状态": "开放申购",
                        "赎回状态": "开放赎回",
                        "下一开放日": "2026-07-29",
                        "购买起点": 10,
                        "日累计限定金额": 1000000,
                    },
                ),
                (1, {"基金代码": "", "基金简称": "坏行"}),
            ]
        )

    def fund_overview_em(self, *, symbol):
        self.calls.append(("fund_overview_em", {"symbol": symbol}))
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "基金代码": symbol,
                        "基金简称": "示例混合A",
                        "基金全称": "示例混合型证券投资基金A",
                        "基金管理人": "示例基金",
                    },
                )
            ]
        )

    def fund_fee_em(self, *, symbol, indicator):
        self.calls.append(("fund_fee_em", {"symbol": symbol, "indicator": indicator}))
        if indicator == "交易状态":
            return FakeDataFrame(
                [(0, {"申购状态": "开放申购", "赎回状态": "开放赎回", "下一开放日": "2026-07-29"})]
            )
        if indicator == "申购与赎回金额":
            return FakeDataFrame([(0, {"购买起点": "10元", "日累计限定金额": "100万元"})])
        if indicator == "交易确认日":
            return FakeDataFrame([(0, {"确认规则": "申购 T+1；赎回 T+2"})])
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "适用金额": "小于100万元",
                        "原费率": "1.20%",
                        "天天基金优惠费率": "0.12%",
                    },
                )
            ]
        )


def test_catalog_and_purchase_operations_are_independent_from_legacy_cache(tmp_path) -> None:
    cache = FundCache(tmp_path / "funds.sqlite")
    ak = ProfileAkshare()
    provider = AkshareProvider(ak_module=ak, cache=cache)

    catalog = provider.fetch_fund_catalog(as_of="2026-07-28")

    assert [item.code for item in catalog] == ["000311", "021511", "021580", "510300"]
    mixed = next(item for item in catalog if item.code == "021511")
    assert mixed.catalog_sources == ("fund_name_em", "fund_open_fund_rank_em")
    etf = next(item for item in catalog if item.code == "510300")
    assert etf.exchange_traded is True
    assert cache.load_funds(allow_stale=True) == []
    assert [trace.endpoint for trace in provider.last_health.endpoints] == [
        "fund_name_em",
        "fund_open_fund_rank_em",
        "fund_etf_spot_em",
    ]

    rules = provider.fetch_purchase_statuses(as_of="2026-07-28")

    assert len(rules) == 1
    assert rules[0].code == "021511"
    assert rules[0].minimum_purchase_amount == "10"
    assert rules[0].daily_purchase_limit == "1000000"
    assert cache.load_funds(allow_stale=True) == []
    assert cache.load_fund_details(allow_stale=True) == []
    assert provider.last_health.endpoints[0].endpoint == "fund_purchase_em"


def test_single_fund_profile_operations_only_call_code_scoped_endpoints(tmp_path) -> None:
    ak = ProfileAkshare()
    provider = AkshareProvider(
        ak_module=ak,
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    profile = provider.fetch_fund_profile("021511", as_of="2026-07-28")
    rule = provider.fetch_fund_trading_rule("021511", as_of="2026-07-28")
    fees = provider.fetch_fund_fees("021511", as_of="2026-07-28")

    assert profile.fund_company == "示例基金"
    assert rule.purchase_status == "开放申购"
    assert rule.redemption_status == "开放赎回"
    assert rule.next_open_date == "2026-07-29"
    assert rule.minimum_purchase_amount == "10元"
    assert rule.daily_purchase_limit == "100万元"
    assert rule.confirmation_rule == "申购 T+1；赎回 T+2"
    assert len(fees) == 3
    assert {fee.fee_type for fee in fees} == {"申购费率（前端）", "赎回费率", "运作费用"}
    called_names = [name for name, _kwargs in ak.calls]
    assert "fund_name_em" not in called_names
    assert "fund_purchase_em" not in called_names
    assert called_names == [
        "fund_overview_em",
        "fund_fee_em",
        "fund_fee_em",
        "fund_fee_em",
        "fund_fee_em",
        "fund_fee_em",
        "fund_fee_em",
    ]
