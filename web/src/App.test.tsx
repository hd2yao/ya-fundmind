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

  it("renders the product boundary and overview route", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "研究总览" })).toBeInTheDocument();
    expect(screen.getByText(/本地基金与 ETF 投研工作台/)).toBeInTheDocument();
    expect(screen.getByText(/不构成买卖建议/)).toBeInTheDocument();
  });

  it("renders a recoverable not-found route", () => {
    render(
      <MemoryRouter initialEntries={["/unknown"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "页面不存在" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回研究总览" })).toHaveAttribute("href", "/");
  });
});
