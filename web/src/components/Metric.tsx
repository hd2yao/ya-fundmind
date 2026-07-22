import type { ReactNode } from "react";

export function Metric({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="metric">
      <span className="metric__label">{label}</span>
      <strong className="metric__value">{value}</strong>
      {detail ? <span className="metric__detail">{detail}</span> : null}
    </div>
  );
}
