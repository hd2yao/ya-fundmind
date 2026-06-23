from fund_agent.cache import FundCache
from fund_agent.providers import AkshareProvider


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class FakeAkshare:
    def fund_open_fund_rank_em(self, symbol):
        assert symbol == "全部"
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "基金代码": " 510300 ",
                        "基金简称": "沪深300ETF",
                        "基金类型": "ETF",
                        "单位净值": "4.0123",
                        "日期": "2026-06-21",
                        "估值日期": "2026-06-22",
                        "近1周": "1.2%",
                        "近1月": "3.4%",
                        "近3月": "5.6%",
                        "近6月": "7.8%",
                        "近1年": "9.1%",
                        "规模": "120.5",
                    },
                ),
                (
                    1,
                    {
                        "基金代码": "000311",
                        "基金简称": "华夏沪深300ETF联接A",
                        "基金类型": "ETF联接",
                        "最新净值": "1.42",
                        "净值日期": "2026-06-21 15:00:00",
                        "近1月": "3.4%",
                    },
                ),
                (2, {"基金代码": "", "基金简称": ""}),
            ]
        )

    def fund_etf_spot_em(self):
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "代码": "510300",
                        "名称": "沪深300ETF华泰柏瑞",
                        "最新价": "5.079",
                        "IOPV实时估值": "5.074",
                        "涨跌幅": "-0.24",
                        "总市值": "134731078002",
                        "数据日期": "2026-06-23 00:00:00",
                        "更新时间": "2026-06-23 09:30:10+08:00",
                    },
                ),
            ]
        )


def test_akshare_live_rows_are_standardized_and_written_to_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = AkshareProvider(ak_module=FakeAkshare(), cache=cache, cache_ttl_days=2)

    funds = provider.fetch_funds(as_of="2026-06-22")

    by_code = {fund.code: fund for fund in funds}
    assert set(by_code) == {"510300", "000311"}
    assert by_code["510300"].name == "沪深300ETF华泰柏瑞"
    assert by_code["510300"].category == "ETF"
    assert by_code["510300"].nav == 5.074
    assert by_code["510300"].price == 5.079
    assert by_code["510300"].valuation_date == "2026-06-23"
    assert by_code["510300"].exchange_traded is True
    assert by_code["510300"].scale_billion == 1347.31078002
    assert by_code["000311"].returns["1m"] == 3.4
    assert by_code["000311"].source == "akshare"
    assert by_code["000311"].metadata["as_of"] == "2026-06-22"
    assert by_code["000311"].metadata["stale"] is False
    assert by_code["000311"].metadata["provider"] == "akshare"
    assert by_code["000311"].metadata["updated_at"]
    assert by_code["000311"].metadata["expires_at"]

    cached = cache.load_funds(as_of="2026-06-22")
    assert [fund.code for fund in cached] == ["000311", "510300"]
    assert cached[0].source == "cache:akshare"
    assert cached[0].metadata["cache_as_of"] == "2026-06-22"
