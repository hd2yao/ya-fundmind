import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { FundsPage } from "./FundsPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    details: {
      as_of: "2026-07-15",
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
          as_of: "2026-07-15",
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
          as_of: "2026-07-15",
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

describe("FundsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("labels watchlist data and supports code/name filtering", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<FundsPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "自选研究" })).toBeInTheDocument());
    expect(screen.getByText("自选池 2")).toBeInTheDocument();
    expect(screen.getByText("宏利半导体产业混合发起C")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "搜索自选基金" }), { target: { value: "021580" } });
    expect(screen.queryByText("宏利半导体产业混合发起C")).not.toBeInTheDocument();
    expect(screen.getByText("华夏人工智能ETF联接D")).toBeInTheDocument();
  });

  it("shows missing fields in detail without turning them into a positive signal", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<FundsPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: "查看021511详情" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "查看021511详情" }));

    expect(screen.getByRole("dialog", { name: "021511 基金详情" })).toBeInTheDocument();
    expect(screen.getByText("fund_manager · rating")).toBeInTheDocument();
    expect(screen.getByText(/缺失字段不会形成正向信号/)).toBeInTheDocument();
  });
});
