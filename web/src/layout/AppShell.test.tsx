import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { App } from "../App";

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="当前测试地址">{`${location.pathname}${location.search}`}</output>;
}

describe("AppShell", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders all research workspaces and marks the current route", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <App />
      </MemoryRouter>
    );

    const labels = [
      "行情总览",
      "基金终端",
      "组合",
      "研究证据",
      "研究助手",
      "人工审核",
      "系统状态",
      "报告中心"
    ];
    for (const label of labels) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByText("数据终端")).toBeInTheDocument();
    expect(screen.getByText("研究工具")).toBeInTheDocument();
    expect(screen.getByText("系统")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "行情总览" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("研究工作区 · 行情总览")).toBeInTheDocument();
    expect(screen.getByText("本地研究工作区")).toBeInTheDocument();
  });

  it("sends the global fund search to the fund terminal", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <App />
        <LocationProbe />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByRole("searchbox", { name: "全局搜索基金" }), {
      target: { value: "510300" }
    });
    fireEvent.submit(screen.getByRole("searchbox", { name: "全局搜索基金" }).closest("form")!);

    expect(screen.getByLabelText("当前测试地址")).toHaveTextContent("/funds?q=510300");
  });

  it("reflects a fund terminal URL query in the global search", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    render(
      <MemoryRouter initialEntries={["/funds?q=510300"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("searchbox", { name: "全局搜索基金" })).toHaveValue("510300");
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
    expect(document.querySelector(".workspace")).toHaveAttribute("inert");
    expect(screen.getByRole("button", { name: "关闭导航" })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole("navigation", { name: "主要导航" }), { key: "Escape" });
    expect(document.querySelector(".primary-nav")).toHaveAttribute("data-mobile-open", "false");
    expect(sidebar).toHaveAttribute("inert");
    expect(document.querySelector(".workspace")).not.toHaveAttribute("inert");
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
