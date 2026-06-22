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
                    },
                ),
                (2, {"基金代码": "", "基金简称": ""}),
            ]
        )


def test_akshare_live_rows_are_standardized_and_written_to_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = AkshareProvider(ak_module=FakeAkshare(), cache=cache, cache_ttl_days=2)

    funds = provider.fetch_funds(as_of="2026-06-22")

    assert [fund.code for fund in funds] == ["510300", "000311"]
    assert funds[0].name == "沪深300ETF"
    assert funds[0].category == "ETF"
    assert funds[0].nav == 4.0123
    assert funds[0].nav_date == "2026-06-21"
    assert funds[0].valuation_date == "2026-06-22"
    assert funds[0].returns["1m"] == 3.4
    assert funds[0].source == "akshare"
    assert funds[0].metadata["as_of"] == "2026-06-22"
    assert funds[0].metadata["stale"] is False
    assert funds[0].metadata["provider"] == "akshare"

    cached = cache.load_funds(as_of="2026-06-22")
    assert [fund.code for fund in cached] == ["000311", "510300"]
    assert cached[0].source == "cache:akshare"
    assert cached[0].metadata["cache_as_of"] == "2026-06-22"
