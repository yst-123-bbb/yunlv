import type { ReactNode } from "react";

export default function EmptyState({
  emoji = "🧭",
  title,
  hint,
  action,
}: {
  emoji?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="emptyState">
      <span style={{ fontSize: "36px", lineHeight: 1 }} aria-hidden="true">
        {emoji}
      </span>
      <strong>{title}</strong>
      {hint ? <span className="muted">{hint}</span> : null}
      {action}
    </div>
  );
}