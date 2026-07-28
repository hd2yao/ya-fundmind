import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { WatchlistPage } from "./WatchlistPage";

const watchlistResponse = {
  availability: "available",
  generated_at: "2026-07-28T10:00:00Z",
  data: {
    as_of: "2026-07-28",
    detail_count: 2,
    coverage_ratio: 0.67,
    data_status: {
      state: "attention",
      label: "请留意数据日期",
      description: "当前展示截至 2026-07-28 的数据，最新更新仍待确认。",
      as_of: "2026-07-28"
    },
    funds: [
      {
        code: "021511",
        name: "宏利半导体产业混合发起C",
        fund_type: "基金",
        primary_theme: "半导体",
        nav: 2.9704,
        return_windows: { "1m": { total_return: 9.99 }, "3m": { total_return: 46.61 } },
        coverage_ratio: 0.67,
        data_status: { state: "attention", label: "请留意数据日期", description: "当前展示截至 2026-07-28 的数据，最新更新仍待确认。", as_of: "2026-07-28" }
      },
      {
        code: "021580",
        name: "华夏人工智能ETF联接D",
        fund_type: "基金",
        primary_theme: "人工智能",
        nav: 1.8126,
        return_windows: { "1m": { total_return: 3.65 }, "3m": { total_return: 22.8 } },
        coverage_ratio: 1,
        data_status: { state: "updated", label: "数据已更新", description: "当前展示截至 2026-07-28 的结构化数据。", as_of: "2026-07-28" }
      }
    ]
  }
};

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="当前测试地址">{`${location.pathname}${location.search}`}</output>;
}

function renderWatchlist() {
  const fetchMock = vi.fn().mockImplementation((input: string | URL) => {
    if (String(input) === "/api/product/watchlist") {
      return Promise.resolve({ ok: true, json: async () => watchlistResponse });
    }
    throw new Error(`Unexpected request: ${input}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <MemoryRouter initialEntries={["/watchlist"]}>
      <WatchlistPage />
      <LocationProbe />
    </MemoryRouter>
  );
  return fetchMock;
}

describe("WatchlistPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the configured watchlist from the read-only product endpoint", async () => {
    const fetchMock = renderWatchlist();

    expect(await screen.findByRole("heading", { name: "自选" })).toBeInTheDocument();
    expect(screen.getByText("配置中的观察基金")).toBeInTheDocument();
    expect(screen.getByText("宏利半导体产业混合发起C")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "自选" }).closest(".page-stack")).toHaveTextContent("只读观察");
    expect(fetchMock).toHaveBeenCalledWith("/api/product/watchlist", expect.any(Object));
    expect(screen.queryByText(/AKShare|cache:|SQLite/)).not.toBeInTheDocument();
  });

  it("filters configured funds and retains the detail return path", async () => {
    renderWatchlist();
    await screen.findByText("宏利半导体产业混合发起C");

    fireEvent.change(screen.getByRole("searchbox", { name: "搜索自选基金" }), { target: { value: "人工智能" } });
    expect(screen.queryByText("宏利半导体产业混合发起C")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看021580详情" }));

    await waitFor(() => {
      expect(screen.getByLabelText("当前测试地址")).toHaveTextContent("/funds/021580?return_to=%2Fwatchlist");
    });
  });
});
