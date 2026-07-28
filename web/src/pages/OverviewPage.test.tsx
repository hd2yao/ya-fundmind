import { render, screen, waitFor } from "@testing-library/react";

import { OverviewPage } from "./OverviewPage";

const availableResponse = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    ops_status: {
      ops_ready: true,
      dashboard_ready: true,
      latest_run: { as_of: "2026-07-15", status: "success" },
      daily: { as_of: "2026-07-15", status: "success", data_quality_grade: "warning" },
      latest_market_theme_count: 31,
      watchlist_detail_count: 3,
      latest_portfolio_holding_count: 3,
      main_model_ready: false,
      main_model_blockers: ["insufficient_history"]
    },
    latest_summary_data: { latest_market_persistent_hot_count: 17 },
    review_queue_count: 4,
    review_state_summary: { unresolved_count: 2 },
    not_production_model: true,
    main_score_changed: false,
    main_risk_changed: false
  }
};

describe("OverviewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the latest run, data quality and review workload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => availableResponse }));

    render(<OverviewPage />);

    expect(screen.getByText("正在读取运行状态")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("2026-07-15")).toBeInTheDocument());
    expect(screen.getByText("请留意数据日期")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("当前仍有观察条件待完成")).toBeInTheDocument();
    expect(screen.getByText(/研究分析暂不调整/)).toBeInTheDocument();
    expect(screen.queryByText("insufficient_history")).not.toBeInTheDocument();
  });

  it("shows a recovery command when outputs are missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ availability: "missing", generated_at: null, data: {} })
      })
    );

    render(<OverviewPage />);

    await waitFor(() => expect(screen.getByText("尚无可用的每日研究产物")).toBeInTheDocument());
    expect(screen.getByText(/完成一次日常更新后再查看/)).toBeInTheDocument();
  });
});
