from __future__ import annotations

from fund_agent.providers import (
    _fund_fees_from_akshare_rows,
    _fund_profile_from_akshare_row,
)


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
