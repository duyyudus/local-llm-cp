import { formatGiB } from "../../lib/format";
import { Sparkline } from "./Sparkline";

export function Meter({
  label,
  value,
  fraction,
  history,
  max,
  historyLabel,
}: {
  label: string;
  value: string;
  fraction: number | null;
  history: (number | null)[];
  max: number;
  historyLabel: string;
}) {
  const percent = fraction == null ? 0 : Math.max(0, Math.min(1, fraction)) * 100;
  return (
    <div className="grid grid-cols-[1fr_7.5rem] items-end gap-3">
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">{label}</span>
          <span className="font-mono text-xs text-zinc-200">{value}</span>
        </div>
        <div
          aria-label={`${label} ${value}`}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={Math.round(percent)}
          className="mt-1 h-2 overflow-hidden rounded-full bg-zinc-800"
          role="progressbar"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
      <Sparkline label={historyLabel} max={max} values={history} />
    </div>
  );
}

export function summarize(values: (number | null)[], unit: string): string {
  const numbers = values.filter((value): value is number => value != null);
  if (numbers.length === 0) return "no samples";
  const peak = Math.max(...numbers);
  return `peak ${unit === "GiB" ? formatGiB(peak) : peak.toFixed(0)} ${unit} over ${values.length}s`;
}
