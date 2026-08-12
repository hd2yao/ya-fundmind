import {
  getFundDetail,
  getFundHistory,
  getMarketIndexHistory,
  getMarketSectorHistory,
  getProductMarketIndexHistory,
  getProductMarketSectorHistory,
  getResource,
  postResource,
  searchFunds,
  searchMarketSectors,
  searchProductMarketSectors
} from "./client";

describe("API client response validation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("rejects a resource with null data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ availability: "available", generated_at: null, data: null })
      })
    );

    await expect(getResource("/api/funds")).rejects.toThrow("invalid resource payload");
  });

  it("rejects a non-object write response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ["legacy"]
      })
    );

    await expect(postResource("/api/reviews/r1", { status: "open" })).rejects.toThrow(
      "invalid resource payload"
    );
  });

  it("serializes fund search filters without undefined values", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        availability: "available",
        items: [],
        page: 2,
        page_size: 25,
        total: 0,
        total_pages: 0,
        facets: { fund_types: {}, themes: {}, exchange_traded: {}, purchase_statuses: {}, data_states: {} },
        data_date: "2026-07-21",
        data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-21" }
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchFunds({
      q: "人工 智能",
      fundType: "ETF",
      purchaseStatus: "开放申购",
      exchangeTraded: true,
      page: 2,
      pageSize: 25,
      sort: "return_1m",
      direction: "desc"
    });

    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).toContain("q=%E4%BA%BA%E5%B7%A5+%E6%99%BA%E8%83%BD");
    expect(requestedUrl).toContain("fund_type=ETF");
    expect(requestedUrl).toContain("purchase_status=%E5%BC%80%E6%94%BE%E7%94%B3%E8%B4%AD");
    expect(requestedUrl).toContain("exchange_traded=true");
    expect(requestedUrl).toContain("page=2");
    expect(requestedUrl).not.toContain("theme=undefined");
  });

  it("loads encoded fund detail and surfaces the API error message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          fund: { code: "510300", name: "沪深300ETF华泰柏瑞", data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-21" } },
          research: {}
        })
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: { message: "Fund is not present in the market index." } })
      });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getFundDetail("510300")).resolves.toMatchObject({ fund: { code: "510300" } });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/product/funds/510300");
    await expect(getFundDetail("999999")).rejects.toThrow("Fund is not present");
  });

  it("loads a validated fund history window", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: "021511",
        range: "3m",
        point_count: 1,
        points: [
          {
            date: "2026-07-21",
            unit_nav: 2.9699,
            accumulated_nav: 2.9699,
            daily_return: 1.2,
            data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-21" }
          }
        ],
        data_date: "2026-07-21",
        data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-21" }
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const history = await getFundHistory("021511", "3m");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/product/funds/021511/history?range=3m");
    expect(history.points[0].unit_nav).toBe(2.9699);
  });

  it("loads a validated market index history window", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        symbol: "000300",
        name: "沪深300",
        series_type: "index",
        range: "6m",
        point_count: 1,
        points: [
          {
            date: "2026-07-22",
            open: 4620,
            close: 4652.8,
            high: 4660,
            low: 4612,
            volume: 130000,
            turnover: 1000000000,
            change_pct: 0.71,
            source: "cache:akshare"
          }
        ],
        source: "cache:akshare",
        as_of: "2026-07-22",
        stale: false,
        fallback_used: false,
        data_quality_grade: "normal",
        warnings: [],
        not_production_model: true,
        main_score_changed: false,
        main_risk_changed: false
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const history = await getMarketIndexHistory("000300", "6m");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/market/indices/000300/history?range=6m"
    );
    expect(history.points[0].close).toBe(4652.8);
  });

  it("serializes industry sector search and validates the catalog", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [{ symbol: "BK1036", name: "半导体", entity_type: "industry" }],
        page: 1,
        page_size: 10,
        total: 1,
        total_pages: 1,
        query: "半导体",
        source: "cache:akshare",
        stale: false,
        fallback_used: false,
        data_quality_grade: "normal",
        warnings: []
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchMarketSectors({
      q: "半导体",
      page: 1,
      pageSize: 10
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/market/sectors?q=%E5%8D%8A%E5%AF%BC%E4%BD%93&page=1&page_size=10"
    );
    expect(result.items[0].symbol).toBe("BK1036");
  });

  it("loads a validated industry sector history window", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        symbol: "BK1036",
        name: "半导体",
        series_type: "industry",
        range: "3m",
        point_count: 1,
        points: [
          {
            date: "2026-07-22",
            close: 1823.4,
            turnover_rate: 2.3,
            source: "cache:akshare"
          }
        ],
        source: "cache:akshare",
        as_of: "2026-07-22",
        stale: false,
        fallback_used: false,
        data_quality_grade: "normal",
        warnings: [],
        not_production_model: true,
        main_score_changed: false,
        main_risk_changed: false
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const history = await getMarketSectorHistory("BK1036", "3m");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/market/sectors/BK1036/history?range=3m"
    );
    expect(history.points[0].turnover_rate).toBe(2.3);
  });

  it("loads product market subresources without requiring legacy diagnostics", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          availability: "missing",
          symbol: "000300",
          name: "沪深300",
          range: "6m",
          point_count: 0,
          required_points: null,
          points: [],
          data_date: null,
          data_status: { state: "unavailable", label: "暂未获取到数据", description: "暂无数据", as_of: null }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          availability: "available",
          items: [{ symbol: "BK1036", name: "半导体", latest: 1823.4, change_pct: 1.2, rise_count: 10, fall_count: 3, leader_name: "示例", leader_change_pct: 2.3 }],
          page: 1,
          page_size: 10,
          total: 1,
          total_pages: 1,
          query: "半导体",
          data_date: "2026-07-27",
          data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-27" }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          availability: "available",
          symbol: "BK1036",
          name: "半导体",
          range: "3m",
          point_count: 1,
          required_points: 60,
          points: [{ date: "2026-07-27", open: null, close: 1823.4, high: null, low: null, volume: null, turnover: null, change_pct: 1.2 }],
          data_date: "2026-07-27",
          data_status: { state: "updated", label: "数据已更新", description: "已更新", as_of: "2026-07-27" }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getProductMarketIndexHistory("000300", "6m")).resolves.toMatchObject({ availability: "missing", points: [] });
    await expect(searchProductMarketSectors({ q: "半导体", page: 1, pageSize: 10 })).resolves.toMatchObject({ total: 1 });
    await expect(getProductMarketSectorHistory("BK1036", "3m")).resolves.toMatchObject({ point_count: 1 });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/product/market/indices/000300/history?range=6m",
      "/api/product/market/sectors?q=%E5%8D%8A%E5%AF%BC%E4%BD%93&page=1&page_size=10",
      "/api/product/market/sectors/BK1036/history?range=3m"
    ]);
  });
});
