import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { CopilotPage } from "./CopilotPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    answer: {
      answer_status: "partial",
      as_of: "2026-07-15",
      summary: "半导体主题有观察性变化，但新闻证据仍不足。",
      confidence: "medium",
      review_required: true
    },
    view_model: {
      status: "partial",
      tone: "warning",
      summary: "半导体主题有观察性变化，但新闻证据仍不足。",
      as_of: "2026-07-15",
      intent: "market_overview",
      confidence: "medium",
      review_required: true,
      finding_count: 1,
      evidence_count: 1,
      findings: [
        {
          finding_id: "f1",
          label: "半导体主题",
          value: "观察到近期变化",
          quality_grade: "warning",
          citations: [
            { evidence_id: "e1", source: "market_intelligence", as_of: "2026-07-15", quality_grade: "warning", stale: false }
          ]
        }
      ],
      data_gaps: ["news_evidence_insufficient"],
      warnings: ["manual_review_required"]
    }
  }
};

describe("CopilotPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits a research question and renders citations and data gaps", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response });
    vi.stubGlobal("fetch", fetchMock);
    render(<CopilotPage />);

    fireEvent.change(screen.getByLabelText("研究问题"), { target: { value: "半导体近期有什么变化？" } });
    fireEvent.click(screen.getByRole("button", { name: "生成证据化回答" }));

    await waitFor(() => expect(screen.getByText("半导体主题有观察性变化，但新闻证据仍不足。")).toBeInTheDocument());
    expect(screen.getByText("market_intelligence")).toBeInTheDocument();
    expect(screen.getByText("news_evidence_insufficient")).toBeInTheDocument();
    expect(screen.getByText(/当前回答不改变主评分或主风险/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/copilot/ask",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ question: "半导体近期有什么变化？" }) })
    );
  });
});
