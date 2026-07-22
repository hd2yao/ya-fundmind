import { getFundDetail, getResource, postResource, searchFunds } from "./client";

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
        facets: { fund_types: {}, themes: {}, exchange_traded: {}, qualities: {} },
        as_of: "2026-07-21",
        source: "akshare",
        data_quality_grade: "normal",
        index_stale: false,
        warnings: []
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchFunds({
      q: "人工 智能",
      fundType: "ETF",
      exchangeTraded: true,
      page: 2,
      pageSize: 25,
      sort: "return_1m",
      direction: "desc"
    });

    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).toContain("q=%E4%BA%BA%E5%B7%A5+%E6%99%BA%E8%83%BD");
    expect(requestedUrl).toContain("fund_type=ETF");
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
          fund: { code: "510300", name: "沪深300ETF华泰柏瑞" },
          research_detail: {},
          not_production_model: true,
          main_score_changed: false,
          main_risk_changed: false
        })
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: { message: "Fund is not present in the market index." } })
      });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getFundDetail("510300")).resolves.toMatchObject({ fund: { code: "510300" } });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/funds/510300");
    await expect(getFundDetail("999999")).rejects.toThrow("Fund is not present");
  });
});
