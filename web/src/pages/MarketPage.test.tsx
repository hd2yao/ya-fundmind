import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MarketPage } from "./MarketPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    as_of: "2026-07-15",
    coverage: { fund_count: 21530, etf_count: 3529 },
    data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-15 的数据，最新更新仍待确认。", as_of: "2026-07-15" },
    themes: [
        {
          name: "医药",
          returns: { "1w": 7.43, "1m": 16.72, "3m": 0.17 },
          positive_ratio_1m: 0.852,
          sample_size: 527,
          data_status: { state: "updated", label: "数据已更新", description: "当前展示截至 2026-07-15 的结构化数据。", as_of: "2026-07-15" }
        }
    ],
    trend: {
      persistent: [{ name: "医药", rank: 1, rank_change: 2 }],
      new: [{ name: "低波", rank: 14, rank_change: null }],
      rising: [{ name: "QDII", rank: null, rank_change: 11 }],
      falling: []
    }
  }
};

const indexHistory = {
  availability: "available",
  symbol: "000300",
  name: "沪深300",
  range: "6m",
  point_count: 3,
  required_points: 120,
  points: [
    { date: "2026-07-18", open: 4580, close: 4600, high: 4610, low: 4570, volume: 100000, turnover: 800000000, change_pct: -0.2 },
    { date: "2026-07-21", open: 4600, close: 4620, high: 4630, low: 4590, volume: 120000, turnover: 900000000, change_pct: 0.52 },
    { date: "2026-07-22", open: 4620, close: 4652.8, high: 4660, low: 4612, volume: 130000, turnover: 1000000000, change_pct: 0.71 }
  ],
  data_date: "2026-07-22",
  data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-22 的数据，最新更新仍待确认。", as_of: "2026-07-22" }
};

const sectorCatalog = {
  availability: "available",
  items: [
    {
      symbol: "BK1036",
      name: "半导体",
      latest: 1823.4,
      change_pct: 2.31,
      turnover_rate: 3.25,
      rise_count: 41,
      fall_count: 6,
      leader_name: "示例股份"
    }
  ],
  page: 1,
  page_size: 12,
  total: 1,
  total_pages: 1,
  query: "",
  data_date: "2026-07-22",
  data_status: { state: "updated", label: "数据已更新", description: "当前展示截至 2026-07-22 的结构化数据。", as_of: "2026-07-22" }
};

const sectorHistory = {
  availability: "available",
  symbol: "BK1036",
  name: "半导体",
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
      change_pct: 0.56
    },
    {
      date: "2026-07-22",
      open: 1810,
      close: 1823.4,
      high: 1830,
      low: 1802,
      volume: 130000,
      turnover: 1000000000,
      change_pct: 0.74
    }
  ],
  data_date: "2026-07-22",
  data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-22 的数据，最新更新仍待确认。", as_of: "2026-07-22" }
};

function stubMarketApi(
  marketResponse: unknown = response,
  sectorResponse: unknown = sectorCatalog
) {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    const url = String(input);
    if (url === "/api/product/market") {
      return Promise.resolve({ ok: true, json: async () => marketResponse });
    }
    if (url.startsWith("/api/product/market/indices/")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      const symbol = url.split("/")[5];
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
    if (url.startsWith("/api/product/market/sectors/") && url.includes("/history")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      return Promise.resolve({
        ok: true,
        json: async () => ({ ...sectorHistory, range })
      });
    }
    if (url.startsWith("/api/product/market/sectors")) {
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

  it("shows a product-facing market surface without engineering diagnostics", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    await waitFor(() => expect(screen.getByText("21,530")).toBeInTheDocument());
    expect(screen.getByRole("navigation", { name: "行情数据区域" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "主要指数" })).toHaveAttribute("href", "#market-index");
    expect(screen.getByRole("link", { name: "行业板块" })).toHaveAttribute("href", "#market-sector-title");
    expect(screen.getByRole("link", { name: "主题窗口" })).toHaveAttribute("href", "#top-theme-title");
    expect(screen.getByText("3,529")).toBeInTheDocument();
    expect(screen.getAllByText("医药").length).toBeGreaterThan(0);
    expect(screen.getByText("QDII")).toBeInTheDocument();
    expect(screen.getByText("低波")).toBeInTheDocument();
    expect(screen.getByText("全市场观察，不是自选或持仓建议")).toBeInTheDocument();
    expect(screen.getByText("交易数据日期")).toBeInTheDocument();
    expect(screen.getByText("资料状态")).toBeInTheDocument();
    expect(screen.getAllByText("请留意数据日期").length).toBeGreaterThan(0);
    expect(screen.queryByText("质量趋势")).not.toBeInTheDocument();
    expect(screen.queryByText("akshare")).not.toBeInTheDocument();
    expect(screen.queryByText("cache:akshare")).not.toBeInTheDocument();
    expect(screen.queryByText("normal")).not.toBeInTheDocument();
    expect(screen.queryByText("warning")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "搜索医药同名行业板块" })
    );
    expect(screen.getByLabelText("搜索行业板块")).toHaveValue("医药");
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(
        urls.some((url) =>
          url.includes(
            "/api/product/market/sectors?q=%E5%8C%BB%E8%8D%AF"
          )
        )
      ).toBe(true);
    });
  });

  it("refreshes market resources without exposing local implementation details", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    await screen.findByRole("img", { name: "沪深300 指数日线图" });
    fireEvent.click(screen.getByRole("button", { name: "刷新行情" }));

    await waitFor(() => {
      const marketCalls = fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url === "/api/product/market");
      expect(marketCalls).toHaveLength(2);
    });
    expect(screen.getByText("交易数据日期")).toBeInTheDocument();
    expect(screen.getByText("资料状态")).toBeInTheDocument();
  });

  it("shows real index history and switches symbol and range", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    expect(await screen.findByRole("img", { name: "沪深300 指数日线图" })).toBeInTheDocument();
    expect(screen.getAllByText("4,652.80").length).toBeGreaterThan(0);
    expect(screen.queryByText(/cache:akshare/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创业板指" }));
    fireEvent.click(screen.getByRole("button", { name: "1 月" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(
        urls.some((url) =>
          url.endsWith("/api/product/market/indices/399006/history?range=1m")
        )
      ).toBe(true);
    });
  });

  it("selects an industry row directly and opens its history curve", async () => {
    const fetchMock = stubMarketApi();

    render(<MarketPage />);

    expect(await screen.findByText("行业板块行情")).toBeInTheDocument();
    expect(screen.getByText("BK1036")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("row", { name: /半导体.*BK1036/ }));

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
            "/api/product/market/sectors?q=%E5%8D%8A%E5%AF%BC%E4%BD%93"
          )
        )
      ).toBe(true);
    });
  });

  it("supports keyboard selection for an industry history", async () => {
    stubMarketApi();

    render(<MarketPage />);

    const row = await screen.findByRole("row", { name: /半导体.*BK1036/ });
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });

    expect(
      await screen.findByRole("img", { name: "半导体 行业板块日线图" })
    ).toBeInTheDocument();
  });

  it("does not invent themes when market data is missing", async () => {
    stubMarketApi(
      {
        availability: "missing",
        generated_at: null,
        data: { as_of: null, coverage: { fund_count: null, etf_count: null }, data_status: { state: "unavailable", label: "暂未获取到数据", description: "暂无数据", as_of: null }, themes: [], trend: { persistent: [], new: [], rising: [], falling: [] } }
      }
    );

    render(<MarketPage />);

    await waitFor(() => expect(screen.getByText("尚无市场情报产物")).toBeInTheDocument());
    expect(await screen.findByRole("img", { name: "沪深300 指数日线图" })).toBeInTheDocument();
    expect(screen.queryByText("热门板块")).not.toBeInTheDocument();
  });

  it("translates degraded market quality into a user-facing attention prompt", async () => {
    stubMarketApi({
      ...response,
      data: {
        ...response.data,
        data_status: { state: "limited", label: "资料暂不完整", description: "当前展示截至 2026-07-15 的数据，部分资料尚待补充。", as_of: "2026-07-15" }
      }
    });

    render(<MarketPage />);

    const labels = await screen.findAllByText("资料暂不完整");
    expect(labels.some((element) => element.classList.contains("status-badge--critical"))).toBe(true);
  });

  it("explains sector data that needs attention without leaking cache terminology", async () => {
    stubMarketApi(response, {
      ...sectorCatalog,
      data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-22 的数据，最新更新仍待确认。", as_of: "2026-07-22" }
    });

    render(<MarketPage />);

    expect(await screen.findByText("行业板块行情")).toBeInTheDocument();
    expect(screen.getByText("BK1036")).toBeInTheDocument();
    await waitFor(() => {
      expect(document.querySelector(".market-data-note"))
        .toHaveTextContent("当前展示截至 2026-07-22 的数据，最新更新仍待确认。");
    });
    expect(screen.queryByText("cache fallback")).not.toBeInTheDocument();
    expect(screen.queryByText("stale")).not.toBeInTheDocument();
  });
});
