import type { ReactNode } from "react";

export type StatusBadgeTone = "neutral" | "info" | "success" | "warning" | "error";

// Spelled out so Tailwind keeps the classes.
const TONE_CLASS: Record<StatusBadgeTone, string> = {
  neutral: "badge-ghost",
  info: "badge-info",
  success: "badge-success",
  warning: "badge-warning",
  error: "badge-error",
};

export function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: StatusBadgeTone;
}) {
  return (
    <span className={`badge badge-sm ${TONE_CLASS[tone]} gap-1 whitespace-nowrap`}>{children}</span>
  );
}
