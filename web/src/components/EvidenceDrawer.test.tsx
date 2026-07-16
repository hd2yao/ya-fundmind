import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { EvidenceDrawer } from "./EvidenceDrawer";

function DrawerHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>查看证据</button>
      <EvidenceDrawer open={open} title="主题证据" onClose={() => setOpen(false)}>
        <p>结构化来源</p>
      </EvidenceDrawer>
    </>
  );
}

describe("EvidenceDrawer", () => {
  it("supports focus management and Escape close", () => {
    render(<DrawerHarness />);
    const trigger = screen.getByRole("button", { name: "查看证据" });

    trigger.focus();
    fireEvent.click(trigger);

    expect(screen.getByRole("button", { name: "关闭详情" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "主题证据" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
