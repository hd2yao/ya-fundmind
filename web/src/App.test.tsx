import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens the product on the market terminal", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText("FundMind OS · 行情总览")).toBeInTheDocument();
    expect(screen.getByText("正在读取市场情报")).toBeInTheDocument();
    expect(screen.getByText(/基金与市场信息平台/)).toBeInTheDocument();
    expect(screen.getByText(/不构成买卖建议/)).toBeInTheDocument();
  });

  it("renders a recoverable not-found route", () => {
    render(
      <MemoryRouter initialEntries={["/unknown"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "页面不存在" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回行情总览" })).toHaveAttribute("href", "/market");
  });
});
