import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PortfolioPage } from "./PortfolioPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    as_of: "2026-07-15",
    status: "warning",
    portfolio_name: "示例基金 ETF 组合",
    holding_count: 1,
    total_value: null,
    valued_total_value: 0,
    valuation_status: "unavailable",
    valued_position_count: 0,
    unvalued_position_count: 1,
    cash_available: 2000,
    total_unrealized_return_pct: null,
    positions: [
      {
        code: "510300",
        name: "沪深300ETF",
        shares: 800,
        cost_value: 2960,
        current_value: null,
        weight: null,
        source: "akshare",
        primary_theme: "沪深300",
        unrealized_return_pct: null,
        valuation_confidence: null
      }
    ],
    theme_exposure: { "沪深300": { holding_count: 1, current_value: null, weight: null } },
    fund_type_exposure: { ETF: { holding_count: 1, current_value: null, weight: null } },
    observation_issues: [
      { issue_type: "missing_position_valuation", severity: "warning", message: "510300 has no usable current valuation." }
    ],
    warnings: ["portfolio_current_value_unavailable"]
  }
};

describe("PortfolioPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("separates configured holdings from watchlist and handles missing valuations", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<MemoryRouter><PortfolioPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("示例基金 ETF 组合")).toBeInTheDocument());
    expect(screen.getByText(/来自 portfolio 配置/)).toBeInTheDocument();
    expect(screen.getByText("当前估值不可用")).toBeInTheDocument();
    expect(screen.queryByText("-100.00%")).not.toBeInTheDocument();
    expect(screen.getByText(/1 只待估值，不展示误导性收益率/)).toBeInTheDocument();
    expect(screen.getAllByText("权重待估值")).toHaveLength(2);
    expect(screen.getByText("510300 has no usable current valuation.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "510300" })).toHaveAttribute("href", "/funds/510300?return_to=%2Fportfolio");
    expect(screen.getByText(/不生成调仓动作/)).toBeInTheDocument();
  });

  it("shows an available position valuation even when confidence is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          data: {
            ...response.data,
            total_value: 3200,
            positions: [
              {
                code: "510300",
                name: "沪深300ETF",
                shares: 800,
                cost_value: 2960,
                current_value: 3200,
                unrealized_return_pct: 8.11,
                source: "fund_agent_report"
              }
            ],
            observation_issues: [],
            warnings: []
          }
        })
      })
    );

    render(<MemoryRouter><PortfolioPage /></MemoryRouter>);

    const row = await screen.findByRole("row", { name: /510300/ });
    expect(within(row).getByText("¥3,200.00")).toBeInTheDocument();
    expect(within(row).getByText("8.11%")).toBeInTheDocument();
  });

  it("shows comparable type and theme weights only when valuations are available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          data: {
            ...response.data,
            total_value: 3200,
            positions: [{ ...response.data.positions[0], current_value: 3200, unrealized_return_pct: 8.11 }],
            theme_exposure: { "沪深300": { holding_count: 1, current_value: 3200, weight: 1 } },
            fund_type_exposure: { ETF: { holding_count: 1, current_value: 3200, weight: 1 } },
            observation_issues: [],
            warnings: []
          }
        })
      })
    );

    render(<MemoryRouter><PortfolioPage /></MemoryRouter>);

    expect(await screen.findByRole("progressbar", { name: "沪深300 权重" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("progressbar", { name: "ETF 权重" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText("当前没有待处理的组合观察性问题。")).toBeInTheDocument();
  });
});
