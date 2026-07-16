import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";

describe("AppShell", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders all research workspaces and marks the current route", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <App />
      </MemoryRouter>
    );

    const labels = [
      "研究总览",
      "市场情报",
      "自选研究",
      "组合分析",
      "新闻证据",
      "研究助手",
      "人工审核",
      "报告中心"
    ];
    for (const label of labels) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "市场情报" })).toHaveAttribute("aria-current", "page");
  });

  it("opens and closes the responsive navigation", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn()
      })
    );
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    const menuButton = screen.getByRole("button", { name: "打开导航" });
    const sidebar = document.querySelector(".sidebar");
    expect(sidebar).toHaveAttribute("inert");
    expect(sidebar).toHaveAttribute("aria-hidden", "true");

    fireEvent.click(menuButton);

    expect(screen.getByRole("navigation", { name: "主要导航" })).toHaveAttribute("data-mobile-open", "true");
    expect(sidebar).not.toHaveAttribute("inert");
    expect(screen.getByRole("button", { name: "关闭导航" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭导航" }));
    expect(document.querySelector(".primary-nav")).toHaveAttribute("data-mobile-open", "false");
    expect(sidebar).toHaveAttribute("inert");
    expect(menuButton).toHaveFocus();
  });

  it("keeps the research-only boundary visible", () => {
    render(
      <MemoryRouter initialEntries={["/portfolio"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText("仅用于研究观察与人工审核")).toBeInTheDocument();
    expect(screen.getByText(/不自动交易/)).toBeInTheDocument();
  });
});
