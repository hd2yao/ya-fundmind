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

  it("renders readable report metadata without exposing artifact paths", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<ReportsPage />);

    await waitFor(() => expect(screen.getByText("基金研究主报告")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "打开基金研究主报告" })).toHaveAttribute("href", "/api/reports/fund_agent_report");
    expect(screen.getByText("新闻证据").closest("article")).toHaveTextContent("尚未生成");
    expect(screen.getAllByText("网页报告")).toHaveLength(2);
    expect(screen.getByText("文本摘要")).toBeInTheDocument();
    expect(screen.queryByText("latest_summary.md")).not.toBeInTheDocument();
    expect(screen.queryByText("dashboard/news.html")).not.toBeInTheDocument();
    expect(screen.getByText(/报告用于阅读和人工复核/)).toBeInTheDocument();
  });
});
