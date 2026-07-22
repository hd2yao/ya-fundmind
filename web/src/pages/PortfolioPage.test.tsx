import { render, screen, waitFor, within } from "@testing-library/react";

import { PortfolioPage } from "./PortfolioPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    as_of: "2026-07-15",
    status: "warning",
    portfolio_name: "示例基金 ETF 组合",
    holding_count: 1,
    total_value: 0,
    cash_available: 2000,
    total_unrealized_return_pct: -100,
    positions: [
      {
        code: "510300",
        name: "沪深300ETF",
        shares: 800,
        cost_value: 2960,
        current_value: 0,
        weight: 0,
        source: "akshare",
        primary_theme: "沪深300",
        unrealized_return_pct: -100,
        valuation_confidence: null
      }
    ],
    theme_exposure: { "沪深300": { holding_count: 1, current_value: 0, weight: 0 } },
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
    render(<PortfolioPage />);

    await waitFor(() => expect(screen.getByText("示例基金 ETF 组合")).toBeInTheDocument());
    expect(screen.getByText(/来自 portfolio 配置/)).toBeInTheDocument();
    expect(screen.getByText("当前估值不可用")).toBeInTheDocument();
    expect(screen.queryByText("-100.00%")).not.toBeInTheDocument();
    expect(screen.getByText("510300 has no usable current valuation.")).toBeInTheDocument();
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

    render(<PortfolioPage />);

    const row = await screen.findByRole("row", { name: /510300/ });
    expect(within(row).getByText("¥3,200.00")).toBeInTheDocument();
    expect(within(row).getByText("8.11%")).toBeInTheDocument();
  });
});
