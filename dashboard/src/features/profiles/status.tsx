import { CircleAlert, CircleCheck, CircleHelp, CircleStop, LoaderCircle, Play } from "lucide-react";

import type { RunState } from "../../api";
import { StatusBadge, type StatusBadgeTone } from "../../components/StatusBadge";

const STATUS: Record<RunState, { label: string; tone: StatusBadgeTone; icon: typeof Play }> = {
  ready: { label: "ready", tone: "success", icon: CircleCheck },
  starting: { label: "loading", tone: "warning", icon: LoaderCircle },
  running: { label: "running", tone: "info", icon: Play },
  exited: { label: "exited", tone: "error", icon: CircleAlert },
  unknown: { label: "unknown", tone: "neutral", icon: CircleHelp },
  stopped: { label: "stopped", tone: "neutral", icon: CircleStop },
};

export function isActive(status: RunState): boolean {
  return status === "ready" || status === "starting" || status === "running" || status === "unknown";
}

export function RunStatusBadge({ status }: { status: RunState }) {
  const { label, tone, icon: Icon } = STATUS[status];
  return (
    <StatusBadge tone={tone}>
      <Icon className={`h-3 w-3 ${status === "starting" ? "animate-spin" : ""}`} />
      {label}
    </StatusBadge>
  );
}
