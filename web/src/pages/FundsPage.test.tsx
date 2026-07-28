import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { FundsPage } from "./FundsPage";

const searchResponse = {
  availability: "available",
  items: [
    {
      code: "510300",
      name: "沪深300ETF华泰柏瑞",
      fund_type: "ETF",
      primary_theme: "宽基",
      themes: ["宽基", "沪深300"],
      nav: 4.21,
      scale: 520.5,
      exchange_traded: true,
      returns: { "1m": 2.5, "3m": 5, "6m": 8, "1y": 12 },
      data_date: "2026-07-21",
      data_status: { state: "updated", label: "数据已更新", description: "当前展示截至 2026-07-21 的结构化数据。", as_of: "2026-07-21" }
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
    data_states: { updated: 21570 }
  },
  data_date: "2026-07-21",
  data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-21 的数据，最新更新仍待确认。", as_of: "2026-07-21" }
};

function stubApi() {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    const url = String(input);
    if (url.startsWith("/api/product/funds/search")) {
      return Promise.resolve({ ok: true, json: async () => searchResponse });
    }
    if (url === "/api/product/funds/510300") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          fund: searchResponse.items[0],
          research: {
            fund_company: "华泰柏瑞基金",
            missing_fields: ["rating"],
            coverage: { coverage_ratio: 0.8, label: "部分资料待补充" },
            data_status: searchResponse.data_status,
            return_windows: {},
            is_watchlist: false,
            is_portfolio: false
          }
        })
      });
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
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
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

  it("keeps the fund terminal scoped to server-side market search", async () => {
    const fetchMock = stubApi();
    renderFunds();

    await screen.findByRole("heading", { name: "基金终端" });
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).not.toContain("/api/product/watchlist");
    expect(screen.queryByText("配置中的观察基金")).not.toBeInTheDocument();
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
