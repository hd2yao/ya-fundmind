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

describe("MarketPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows market coverage, theme trend and observation details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));

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

  it("does not invent themes when market data is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ availability: "missing", generated_at: null, data: { intelligence: {}, trend: {} } })
      })
    );

    render(<MarketPage />);

    await waitFor(() => expect(screen.getByText("尚无市场情报产物")).toBeInTheDocument());
    expect(screen.queryByText("热门板块")).not.toBeInTheDocument();
  });
});
