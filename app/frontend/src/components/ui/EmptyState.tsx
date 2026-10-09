import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  icon: LucideIcon;
  /** Reflective one-liner, set in Plex Serif italic. */
  line: string;
  children?: ReactNode;
}

export function EmptyState({ icon: Icon, line, children }: Props) {
  return (
    <div className="empty">
      <span className="empty__icon" aria-hidden="true">
        <Icon size={20} />
      </span>
      <p className="empty__line">{line}</p>
      {children}
    </div>
  );
}
