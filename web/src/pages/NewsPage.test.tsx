import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NewsPage } from "./NewsPage";

const response = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    as_of: "2026-07-15",
    evidence_count: 3,
    low_confidence_count: 1,
    duplicate_count: 0,
    source: "fixture",
    indexed_fund_codes: ["021511"],
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
        related_funds: ["021511", "999999", "not-a-code"],
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
      },
      {
        evidence_id: "e3",
        title: "不安全链接样例",
        published_at: "2026-06-21T00:00:00Z",
        source: "fixture-news",
        source_quality: "verified",
        evidence_strength: "high",
        low_confidence: false,
        related_themes: ["人工智能"],
        related_funds: [],
        url: "javascript:alert('unsafe')",
        warnings: []
      }
    ],
    warnings: ["low_confidence_evidence_present"]
  }
};

describe("NewsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("filters evidence without changing its source data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<MemoryRouter><NewsPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("半导体产业链景气度观察样例")).toBeInTheDocument());
    expect(screen.getByText("Fixture evidence")).toBeInTheDocument();
    expect(screen.getAllByText("low_confidence").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("按主题筛选"), { target: { value: "消费" } });
    expect(screen.queryByText("半导体产业链景气度观察样例")).not.toBeInTheDocument();
    expect(screen.getByText("消费行业基金月度观点样例")).toBeInTheDocument();
    expect(screen.getByText(/没有可核验链接/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("按主题筛选"), { target: { value: "全部主题" } });
    fireEvent.change(screen.getByLabelText("按来源质量筛选"), { target: { value: "verified" } });
    expect(screen.queryByText("消费行业基金月度观点样例")).not.toBeInTheDocument();
    expect(screen.getByText("半导体产业链景气度观察样例")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("按证据强度筛选"), { target: { value: "high" } });
    expect(screen.queryByText("半导体产业链景气度观察样例")).not.toBeInTheDocument();
    expect(screen.getByText("不安全链接样例")).toBeInTheDocument();
    expect(screen.getByText("链接不可安全打开")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索标题、来源或基金代码"), { target: { value: "不存在" } });
    expect(screen.getByText("没有符合当前筛选的证据。请调整文本、主题、来源质量或证据强度。")).toBeInTheDocument();
  });

  it("links only local indexed fund codes and protects evidence URLs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<MemoryRouter><NewsPage /></MemoryRouter>);

    expect(await screen.findByRole("link", { name: "021511" })).toHaveAttribute("href", "/funds/021511?return_to=%2Fnews");
    expect(screen.getByText("999999 · 未索引")).not.toHaveAttribute("href");
    expect(screen.getByText("not-a-code · 代码无效")).not.toHaveAttribute("href");
    const sourceLink = screen.getByRole("link", { name: /打开来源/ });
    expect(sourceLink).toHaveAttribute("href", "https://example.com/e1");
    expect(sourceLink).toHaveAttribute("target", "_blank");
    expect(sourceLink).toHaveAttribute("rel", "noopener noreferrer");
  });
});
