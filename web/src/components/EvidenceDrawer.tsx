import { X } from "lucide-react";
import type { ReactNode } from "react";

export function EvidenceDrawer({
  open,
  title,
  children,
  onClose
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <aside className="evidence-drawer" role="dialog" aria-modal="false" aria-label={title}>
      <div className="drawer-header">
        <div>
          <p className="eyebrow">Structured evidence</p>
          <h2>{title}</h2>
        </div>
        <button className="icon-button" type="button" aria-label="关闭详情" title="关闭详情" onClick={onClose}>
          <X size={20} aria-hidden />
        </button>
      </div>
      <div className="drawer-content">{children}</div>
    </aside>
  );
}
