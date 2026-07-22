import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { NewsPage } from "./NewsPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    as_of: "2026-07-15",
    evidence_count: 2,
    low_confidence_count: 1,
    duplicate_count: 0,
    source: "fixture",
    items: [
      {
        evidence_id: "e1",
        title: "半导体产业链景气度观察样例",
        published_at: "2026-06-23T00:00:00Z",
        source: "fixture-news",
        source_quality: "verified",
        evidence_strength: "medium",
        low_confidence: false,
        related_themes: ["半导体"],
        related_funds: ["021511"],
        url: "https://example.com/e1",
        warnings: []
      },
      {
        evidence_id: "e2",
        title: "消费行业基金月度观点样例",
        published_at: "2026-06-22T00:00:00Z",
        source: "unknown-fixture",
        source_quality: "low_confidence",
        evidence_strength: "low",
        low_confidence: true,
        related_themes: ["消费"],
        related_funds: [],
        url: null,
        warnings: ["low_confidence", "missing_url"]
      }
    ],
    warnings: ["low_confidence_evidence_present"]
  }
};

describe("NewsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows source quality and filters evidence by theme", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<NewsPage />);

    await waitFor(() => expect(screen.getByText("半导体产业链景气度观察样例")).toBeInTheDocument());
    expect(screen.getByText("Fixture evidence")).toBeInTheDocument();
    expect(screen.getByText("low_confidence")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("按主题筛选"), { target: { value: "消费" } });
    expect(screen.queryByText("半导体产业链景气度观察样例")).not.toBeInTheDocument();
    expect(screen.getByText("消费行业基金月度观点样例")).toBeInTheDocument();
    expect(screen.getByText(/没有可核验链接/)).toBeInTheDocument();
  });
});
