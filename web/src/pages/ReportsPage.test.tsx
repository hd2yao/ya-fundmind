import { render, screen, waitFor } from "@testing-library/react";

import { ReportsPage } from "./ReportsPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    reports: [
      { report_id: "latest_summary", label: "最新摘要", relative_path: "latest_summary.md", kind: "md", exists: true, updated_at: "2026-07-16T09:00:00Z" },
      { report_id: "fund_agent_report", label: "基金研究主报告", relative_path: "fund_agent_report.html", kind: "html", exists: true, updated_at: "2026-07-16T09:00:00Z" },
      { report_id: "news", label: "新闻证据", relative_path: "dashboard/news.html", kind: "html", exists: false, updated_at: null }
    ]
  }
};

describe("ReportsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders only allowlisted report metadata and disables missing artifacts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<ReportsPage />);

    await waitFor(() => expect(screen.getByText("基金研究主报告")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "打开基金研究主报告" })).toHaveAttribute("href", "/api/reports/fund_agent_report");
    expect(screen.getByText("新闻证据").closest("article")).toHaveTextContent("尚未生成");
    expect(screen.getByText(/下游集成只读取 JSON contract/)).toBeInTheDocument();
  });
});
