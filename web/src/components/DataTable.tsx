import type { ReactNode } from "react";

export function DataTable({ label, children, minWidth = 760 }: { label: string; children: ReactNode; minWidth?: number }) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      <table className="data-table" style={{ minWidth }}>{children}</table>
    </div>
  );
}
