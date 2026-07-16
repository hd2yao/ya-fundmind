import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ReviewPage } from "./ReviewPage";

const listResponse = {
  availability: "available",
  generated_at: "2026-07-16T10:00:00Z",
  data: {
    queue: [{ review_id: "r1", signal_id: "s1", status: "open", reason: "insufficient_history" }],
    state: [],
    summary: { total_review_items: 0, unresolved_count: 0 }
  }
};

describe("ReviewPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("updates a known review item and keeps the action research-only", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => listResponse })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ availability: "available", generated_at: "2026-07-16T10:01:00Z", data: { review_id: "r1", status: "needs_more_data" } })
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewPage />);

    await waitFor(() => expect(screen.getByText("insufficient_history")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("审核状态 r1"), { target: { value: "needs_more_data" } });
    fireEvent.change(screen.getByLabelText("审核备注 r1"), { target: { value: "等待更多有效运行日" } });
    fireEvent.click(screen.getByRole("button", { name: "保存 r1" }));

    await waitFor(() => expect(screen.getByText("r1 已更新为 needs_more_data")).toBeInTheDocument());
    expect(screen.getByText(/只更新本地 review state/)).toBeInTheDocument();
  });
});
