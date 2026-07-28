import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { FundsPage } from "./FundsPage";

const watchlistResponse = {
  availability: "available",
  generated_at: "2026-07-21T10:00:00Z",
  data: {
    details: {
      as_of: "2026-07-21",
      detail_count: 2,
      missing_count: 1,
      warning_count: 1,
      coverage_summary: { average_coverage_ratio: 0.67 },
      fund_details: [
        {
          code: "021511",
          name: "宏利半导体产业混合发起C",
          fund_type: "基金",
          primary_theme: "半导体",
          nav: 2.9704,
          source: "akshare",
          as_of: "2026-07-21",
          data_quality_grade: "warning",
          missing_fields: ["fund_manager", "rating"],
          return_windows: { "1m": { total_return: 9.99 }, "3m": { total_return: 46.61 } },
          data_coverage: { coverage_ratio: 0.67, status: "partial" }
        },
        {
          code: "021580",
          name: "华夏人工智能ETF联接D",
          fund_type: "基金",
          primary_theme: "人工智能",
          nav: 1.8126,
          source: "akshare",
          as_of: "2026-07-21",
          data_quality_grade: "normal",
          missing_fields: [],
          return_windows: { "1m": { total_return: 3.65 }, "3m": { total_return: 22.8 } },
          data_coverage: { coverage_ratio: 1, status: "complete" }
        }
      ]
    },
    signal_candidates: { summary: { eligible_count: 0, excluded_count: 2, display_only_count: 2 } }
  }
};

const searchResponse = {
  availability: "available",
  items: [
    {
      code: "510300",
      name: "沪深300ETF华泰柏瑞",
      fund_type: "ETF",
      primary_theme: "宽基",
      themes: ["宽基", "沪深300"],
      classification_confidence: 0.95,
      nav: 4.21,
      scale: 520.5,
      exchange_traded: true,
      returns: { "1m": 2.5, "3m": 5, "6m": 8, "1y": 12 },
      source: "akshare",
      as_of: "2026-07-21",
      valuation_date: "2026-07-21",
      updated_at: "2026-07-21T10:00:00Z",
      expires_at: "2026-07-22T10:00:00Z",
      stale: false,
      data_quality_grade: "normal"
    }
  ],
  page: 1,
  page_size: 25,
  total: 21570,
  total_pages: 863,
  facets: {
    fund_types: { ETF: 1200, 基金: 20370 },
    themes: { 宽基: 500, 人工智能: 120 },
    exchange_traded: { true: 1200, false: 20370 },
    qualities: { normal: 21570 }
  },
  as_of: "2026-07-21",
  source: "akshare",
  data_quality_grade: "warning",
  index_stale: false,
  warnings: []
};

const historyResponse = {
  code: "510300",
  range: "6m",
  point_count: 3,
  required_points: 120,
  points: [
    { date: "2026-07-18", unit_nav: 4.1, accumulated_nav: 4.1, daily_return: -0.4, source: "cache:akshare" },
    { date: "2026-07-20", unit_nav: 4.15, accumulated_nav: 4.15, daily_return: 1.22, source: "cache:akshare" },
    { date: "2026-07-21", unit_nav: 4.2, accumulated_nav: 4.2, daily_return: 1.2, source: "cache:akshare" }
  ],
  source: "cache:akshare",
  as_of: "2026-07-21",
  updated_at: "2026-07-21T10:00:00Z",
  expires_at: "2026-07-22T10:00:00Z",
  stale: false,
  fallback_used: false,
  fallback_reason: null,
  data_quality_grade: "warning",
  warnings: [{ code: "insufficient_history", severity: "warning", message: "Only 3 points are available." }],
  not_production_model: true,
  main_score_changed: false,
  main_risk_changed: false
};

function stubApi() {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    const url = String(input);
    if (url.startsWith("/api/funds/search")) {
      return Promise.resolve({ ok: true, json: async () => searchResponse });
    }
    if (url === "/api/funds/510300") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          fund: searchResponse.items[0],
          research_detail: {
            fund_company: "华泰柏瑞基金",
            missing_fields: ["rating"],
            data_coverage: { coverage_ratio: 0.8, status: "partial" }
          },
          not_production_model: true,
          main_score_changed: false,
          main_risk_changed: false
        })
      });
    }
    if (url.startsWith("/api/funds/510300/history?range=")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      return Promise.resolve({
        ok: true,
        json: async () => ({ ...historyResponse, range })
      });
    }
    if (url === "/api/funds") {
      return Promise.resolve({ ok: true, json: async () => watchlistResponse });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderFunds(initialEntry = "/funds") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <FundsPage />
    </MemoryRouter>
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="当前测试地址">{`${location.pathname}${location.search}`}</output>;
}

function renderFundsWithLocation(initialEntry = "/funds") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <FundsPage />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe("FundsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("opens on the full-market view and sends server-side search filters", async () => {
    const fetchMock = stubApi();
    renderFunds();

    await waitFor(() => expect(screen.getByRole("heading", { name: "基金终端" })).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: "全市场" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByText("21,570").length).toBeGreaterThan(0);
    expect(screen.getByText("沪深300ETF华泰柏瑞")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "搜索全市场基金" }), {
      target: { value: "人工智能" }
    });
    fireEvent.change(screen.getByRole("combobox", { name: "基金类型" }), {
      target: { value: "ETF" }
    });

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD"))).toBe(true);
      expect(urls.some((url) => url.includes("fund_type=ETF"))).toBe(true);
    });
  });

  it("uses the global q parameter as the initial market search", async () => {
    const fetchMock = stubApi();

    renderFunds("/funds?q=510300");

    expect(await screen.findByRole("searchbox", { name: "搜索全市场基金" })).toHaveValue("510300");
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("q=510300"))).toBe(true);
    });
  });

  it("keeps the configured watchlist as a separate view", async () => {
    stubApi();
    renderFunds();
    await waitFor(() => expect(screen.getByRole("tab", { name: "我的自选" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("tab", { name: "我的自选" }));

    expect(screen.getByText("配置中的观察基金")).toBeInTheDocument();
    expect(screen.getByText("宏利半导体产业混合发起C")).toBeInTheDocument();
    expect(screen.getByText("仅来自 configs/watchlist.yaml")).toBeInTheDocument();
  });

  it("routes a fund row to a standalone detail URL and preserves the terminal query", async () => {
    stubApi();
    renderFundsWithLocation("/funds?q=510300&fund_type=ETF");

    fireEvent.click(await screen.findByRole("button", { name: "查看510300详情" }));

    expect(screen.getByLabelText("当前测试地址")).toHaveTextContent(
      "/funds/510300?return_to=%2Ffunds%3Fq%3D510300%26fund_type%3DETF"
    );
  });

  it("changes result pages without loading all rows in the browser", async () => {
    const fetchMock = stubApi();
    renderFunds();
    await waitFor(() => expect(screen.getByRole("button", { name: "下一页" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("page=2"))).toBe(true);
    });
  });
});
