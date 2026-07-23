import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MarketPage } from "./MarketPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    intelligence: {
      as_of: "2026-07-15",
      total_funds: 21530,
      total_etfs: 3529,
      source: "akshare",
      data_quality_summary: { grade: "warning", stale_record_count: 0 },
      top_themes: [
        {
          theme: "医药",
          avg_return_1w: 7.43,
          avg_return_1m: 16.72,
          avg_return_3m: 0.17,
          positive_ratio_1m: 0.852,
          sample_size: 527,
          data_quality_grade: "normal",
          warnings: []
        }
      ],
      warnings: ["insufficient_sample_themes:1"]
    },
    trend: {
      latest_as_of: "2026-07-15",
      snapshots_processed: 16,
      enough_market_history: true,
      persistent_hot_themes: [{ theme: "医药", hot_ratio: 0.94, latest_rank: 1, rank_change: 2 }],
      new_hot_themes: [{ theme: "低波", latest_rank: 14 }],
      rising_themes: [{ theme: "QDII", rank_change: 11 }],
      data_quality_trend: [
        { as_of: "2026-07-14", warning_count: 1, insufficient_sample_theme_count: 1 },
        { as_of: "2026-07-15", warning_count: 1, insufficient_sample_theme_count: 1 }
      ]
    }
  }
};

const indexHistory = {
  symbol: "000300",
  name: "沪深300",
  series_type: "index",
  range: "6m",
  point_count: 3,
  required_points: 120,
  points: [
    { date: "2026-07-18", open: 4580, close: 4600, high: 4610, low: 4570, volume: 100000, turnover: 800000000, change_pct: -0.2, source: "cache:akshare" },
    { date: "2026-07-21", open: 4600, close: 4620, high: 4630, low: 4590, volume: 120000, turnover: 900000000, change_pct: 0.52, source: "cache:akshare" },
    { date: "2026-07-22", open: 4620, close: 4652.8, high: 4660, low: 4612, volume: 130000, turnover: 1000000000, change_pct: 0.71, source: "cache:akshare" }
  ],
  source: "cache:akshare",
  as_of: "2026-07-22",
  updated_at: "2026-07-22T10:00:00Z",
  expires_at: "2026-07-23T10:00:00Z",
  stale: false,
  fallback_used: false,
  data_quality_grade: "warning",
  warnings: [{ code: "insufficient_history", severity: "warning", message: "Only 3 points are available." }],
  not_production_model: true,
  main_score_changed: false,
  main_risk_changed: false
};

const sectorCatalog = {
  items: [
    {
      symbol: "BK1036",
      name: "半导体",
      entity_type: "industry",
      latest: 1823.4,
      change_pct: 2.31,
      turnover_rate: 3.25,
      rise_count: 41,
      fall_count: 6,
      leader_name: "示例股份",
      source: "cache:akshare",
      as_of: "2026-07-22",
      stale: false
    }
  ],
  page: 1,
  page_size: 12,
  total: 1,
  total_pages: 1,
  query: "",
  sort: "change_pct_desc",
  source: "cache:akshare",
  as_of: "2026-07-22",
  stale: false,
  fallback_used: false,
  data_quality_grade: "normal",
  warnings: [],
  not_production_model: true,
  main_score_changed: false,
  main_risk_changed: false
};

const sectorHistory = {
  symbol: "BK1036",
  name: "半导体",
  series_type: "industry",
  range: "6m",
  point_count: 2,
  required_points: 120,
  points: [
    {
      date: "2026-07-21",
      open: 1800,
      close: 1810,
      high: 1820,
      low: 1795,
      volume: 123456,
      turnover: 987654321,
      turnover_rate: 2.1,
      change_pct: 0.56,
      source: "cache:akshare"
    },
    {
      date: "2026-07-22",
      open: 1810,
      close: 1823.4,
      high: 1830,
      low: 1802,
      volume: 130000,
      turnover: 1000000000,
      turnover_rate: 2.3,
      change_pct: 0.74,
      source: "cache:akshare"
    }
  ],
  source: "cache:akshare",
  as_of: "2026-07-22",
  updated_at: "2026-07-22T10:00:00Z",
  expires_at: "2026-07-23T10:00:00Z",
  stale: false,
  fallback_used: false,
  data_quality_grade: "warning",
  warnings: [{ code: "insufficient_history", severity: "warning", message: "Only 2 points are available." }],
  not_production_model: true,
  main_score_changed: false,
  main_risk_changed: false
};

function stubMarketApi(
  marketResponse: unknown = response,
  sectorResponse: unknown = sectorCatalog
) {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    const url = String(input);
    if (url === "/api/market") {
      return Promise.resolve({ ok: true, json: async () => marketResponse });
    }
    if (url.startsWith("/api/market/indices/")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      const symbol = url.split("/")[4];
      const names: Record<string, string> = {
        "000001": "上证指数",
        "000300": "沪深300",
        "399006": "创业板指"
      };
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...indexHistory,
          symbol,
          name: names[symbol],
          range
        })
      });
    }
    if (url.startsWith("/api/market/sectors/") && url.includes("/history")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      return Promise.resolve({
        ok: true,
        json: async () => ({ ...sectorHistory, range })
      });
    }
    if (url.startsWith("/api/market/sectors")) {
      const query = new URL(url, "http://localhost").searchParams.get("q") || "";
      return Promise.resolve({
        ok: true,
        json: async () => ({ ...(sectorResponse as object), query })
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("MarketPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows market coverage, theme trend and observation details", async () => {
    stubMarketApi();

    render(<MarketPage />);

    await waitFor(() => expect(screen.getByText("21,530")).toBeInTheDocument());
    expect(screen.getByText("3,529")).toBeInTheDocument();
    expect(screen.getAllByText("医药").length).toBeGreaterThan(0);
    expect(screen.getByText("QDII")).toBeInTheDocument();
    expect(screen.getByText("低波")).toBeInTheDocument();
    expect(screen.getByText("全市场观察，不是自选或持仓建议")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看医药详情" }));
    expect(screen.getByRole("dialog", { name: "医药观察详情" })).toBeInTheDocument();
    expect(screen.getByText("样本 527")).toBeInTheDocument();
  });

  it("shows real index history and switches symbol and range", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    expect(await screen.findByRole("img", { name: "沪深300 指数日线图" })).toBeInTheDocument();
    expect(screen.getAllByText("4,652.80").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/cache:akshare/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "创业板指" }));
    fireEvent.click(screen.getByRole("button", { name: "1 月" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(
        urls.some((url) =>
          url.endsWith("/api/market/indices/399006/history?range=1m")
        )
      ).toBe(true);
    });
  });

  it("searches industry sectors and opens a sector history curve", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    expect(await screen.findByText("行业板块行情")).toBeInTheDocument();
    expect(screen.getByText("BK1036")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "查看半导体走势" })
    );

    expect(
      await screen.findByRole("img", { name: "半导体 行业板块日线图" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("1,823.40").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("搜索行业板块"), {
      target: { value: "半导体" }
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索板块" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(
        urls.some((url) =>
          url.includes(
            "/api/market/sectors?q=%E5%8D%8A%E5%AF%BC%E4%BD%93"
          )
        )
      ).toBe(true);
    });
  });

  it("does not invent themes when market data is missing", async () => {
    stubMarketApi(
      {
        availability: "missing",
        generated_at: null,
        data: { intelligence: {}, trend: {} }
      }
    );

    render(<MarketPage />);

    await waitFor(() => expect(screen.getByText("尚无市场情报产物")).toBeInTheDocument());
    expect(await screen.findByRole("img", { name: "沪深300 指数日线图" })).toBeInTheDocument();
    expect(screen.queryByText("热门板块")).not.toBeInTheDocument();
  });

  it("renders degraded market quality as critical", async () => {
    stubMarketApi({
      ...response,
      data: {
        ...response.data,
        intelligence: {
          ...response.data.intelligence,
          data_quality_summary: {
            grade: "degraded",
            stale_record_count: 4
          }
        }
      }
    });

    render(<MarketPage />);

    expect(await screen.findByText("degraded")).toHaveClass("status-badge--critical");
  });

  it("shows stale sector catalog fallback without hiding market data", async () => {
    stubMarketApi(response, {
      ...sectorCatalog,
      stale: true,
      fallback_used: true,
      data_quality_grade: "warning",
      warnings: [
        {
          code: "stale_cache",
          severity: "warning",
          message: "Industry catalog is served from expired cache."
        }
      ]
    });

    render(<MarketPage />);

    expect(await screen.findByText("行业板块行情")).toBeInTheDocument();
    expect(screen.getByText("BK1036")).toBeInTheDocument();
    expect(screen.getAllByText("cache fallback").length).toBeGreaterThan(0);
    expect(screen.getAllByText("stale").length).toBeGreaterThan(0);
  });
});
