import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

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
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <aside className="evidence-drawer" role="dialog" aria-modal="false" aria-label={title}>
      <div className="drawer-header">
        <div>
          <p className="eyebrow">Structured evidence</p>
          <h2>{title}</h2>
        </div>
        <button ref={closeButtonRef} className="icon-button" type="button" aria-label="关闭详情" title="关闭详情" onClick={onClose}>
          <X size={20} aria-hidden />
        </button>
      </div>
      <div className="drawer-content">{children}</div>
    </aside>
  );
}
