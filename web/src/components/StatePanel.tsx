import { AlertCircle, CircleOff, LoaderCircle, TriangleAlert } from "lucide-react";

type StateKind = "loading" | "empty" | "error" | "degraded";

const stateIcons = {
  loading: LoaderCircle,
  empty: CircleOff,
  error: AlertCircle,
  degraded: TriangleAlert
};

export function StatePanel({
  kind,
  title,
  description
}: {
  kind: StateKind;
  title: string;
  description: string;
}) {
  const Icon = stateIcons[kind];
  return (
    <section className={`state-panel state-panel--${kind}`} aria-live={kind === "loading" ? "polite" : undefined}>
      <Icon size={20} aria-hidden />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </section>
  );
}
