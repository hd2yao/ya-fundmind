import { render, screen } from "@testing-library/react";

import { NewsPage } from "./NewsPage";

describe("NewsPage", () => {
  it("keeps development evidence out of the formal product view", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<NewsPage />);

    expect(screen.getByRole("heading", { name: "研究证据" })).toBeInTheDocument();
    expect(screen.getByText("研究证据暂未开放")).toBeInTheDocument();
    expect(screen.getByText(/可核验且允许展示的公开资料/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/fixture/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/low_confidence/i)).not.toBeInTheDocument();
  });
});
