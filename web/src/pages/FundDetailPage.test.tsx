import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { FundDetailPage } from "./FundDetailPage";

const fund = {
  code: "510300",
  name: "沪深300ETF华泰柏瑞",
  fund_type: "ETF",
  primary_theme: "宽基",
  themes: ["宽基", "沪深300"],
  nav: 4.21,
  scale: 520.5,
  exchange_traded: true,
  returns: { "1m": 2.5, "3m": 5 },
  data_date: "2026-07-21",
  data_status: { state: "updated", label: "数据已更新", description: "当前展示截至 2026-07-21 的结构化数据。", as_of: "2026-07-21" }
};

const history = {
  code: "510300",
  range: "6m",
  point_count: 3,
  required_points: 120,
  points: [
    { date: "2026-07-18", unit_nav: 4.1, accumulated_nav: 4.1, daily_return: -0.4 },
    { date: "2026-07-20", unit_nav: 4.15, accumulated_nav: 4.15, daily_return: 1.22 },
    { date: "2026-07-21", unit_nav: 4.2, accumulated_nav: 4.2, daily_return: 1.2 }
  ],
  data_date: "2026-07-21",
  data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-21 的数据，最新更新仍待确认。", as_of: "2026-07-21" }
};

const profile = {
  fund: { code: "510300", name: "沪深300ETF华泰柏瑞", fund_type: "ETF" },
  profile: {
    full_name: "华泰柏瑞沪深300交易型开放式指数证券投资基金",
    fund_company: "华泰柏瑞基金",
    custodian: "中国工商银行",
    fund_manager: "基金经理",
    inception_date: "2012-05-04",
    asset_scale: 520.5,
    asset_scale_unit: "亿元",
    benchmark: "沪深300指数"
  },
  trading_rule: {
    purchase_status: "开放申购",
    redemption_status: "开放赎回",
    next_open_date: "2026-07-29",
    minimum_purchase_amount: "10元"
  },
  fees: [
    {
      fee_type: "申购费率（前端）",
      condition: "小于100万元",
      period: null,
      channel: "银行卡购买",
      original_rate: "1.20%",
      discounted_rate: "0.12%"
    }
  ],
  data_status: { state: "updated", label: "资料已更新", description: "资料可供浏览。", as_of: "2026-07-28" },
  component_status: {
    profile: { state: "updated", label: "概况已更新", description: "概况资料可供浏览。", as_of: "2026-07-28" },
    trading_rule: { state: "updated", label: "规则已更新", description: "申赎规则可供浏览。", as_of: "2026-07-28" },
    fees: { state: "updated", label: "费率已更新", description: "费率资料可供浏览。", as_of: "2026-07-28" }
  }
};

function stubApi() {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    const url = String(input);
    if (url === "/api/product/funds/510300") {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          fund,
          research: {
            fund_company: "华泰柏瑞基金",
            fund_manager: "基金经理",
            missing_fields: ["基金评级"],
            coverage: { coverage_ratio: 0.8, label: "部分资料待补充" },
            data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-21 的数据，最新更新仍待确认。", as_of: "2026-07-21" },
            return_windows: {},
            is_watchlist: false,
            is_portfolio: false
          }
        })
      });
    }
    if (url.startsWith("/api/product/funds/510300/history?range=")) {
      const range = new URL(url, "http://localhost").searchParams.get("range") || "6m";
      return Promise.resolve({ ok: true, json: async () => ({ ...history, range }) });
    }
    if (url === "/api/product/funds/510300/profile") {
      return Promise.resolve({ ok: true, json: async () => profile });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDetail(entry = "/funds/510300?return_to=%2Ffunds%3Fq%3D510300") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/funds/:code" element={<FundDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("FundDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders accessible profile, NAV and fee tabs without changing research boundaries", async () => {
    const fetchMock = stubApi();
    renderDetail();

    expect(await screen.findByRole("heading", { name: "沪深300ETF华泰柏瑞" })).toBeInTheDocument();
    expect(await screen.findByText("中国工商银行")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "概览" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "净值与业绩" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: "费率与规则" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getAllByText("数据日期").length).toBeGreaterThan(0);
    expect(screen.getByText(/不修改主评分或主风险/)).toBeInTheDocument();
    expect(screen.queryByText("akshare")).not.toBeInTheDocument();
    expect(screen.queryByText("cache:akshare")).not.toBeInTheDocument();
    expect(screen.queryByText("warning")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回上一页" })).toHaveAttribute("href", "/funds?q=510300");

    fireEvent.keyDown(screen.getByRole("tab", { name: "概览" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "净值与业绩" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("img", { name: "510300 历史净值曲线" })).toBeInTheDocument();
    expect(screen.getByText("3 个净值点")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "1 月" }));
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.endsWith("history?range=1m"))).toBe(true);
    });

    fireEvent.click(screen.getByRole("tab", { name: "费率与规则" }));
    expect(screen.getByText("开放申购")).toBeInTheDocument();
    expect(screen.getByText("0.12%")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "510300 历史净值曲线" })).not.toBeInTheDocument();
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.filter((url) => url.endsWith("/profile"))).toHaveLength(1);
  });

  it("keeps invalid direct URLs recoverable", () => {
    renderDetail("/funds/not-a-code");
    expect(screen.getByText("基金代码无效")).toBeInTheDocument();
  });

  it("preserves a safe portfolio return path", async () => {
    stubApi();
    renderDetail("/funds/510300?return_to=%2Fportfolio");

    expect(await screen.findByRole("heading", { name: "沪深300ETF华泰柏瑞" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回上一页" })).toHaveAttribute("href", "/portfolio");
  });
});
