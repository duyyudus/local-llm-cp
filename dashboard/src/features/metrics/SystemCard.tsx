import type { SystemSnapshot } from "../../api";
import { formatGiB } from "../../lib/format";
import { Meter, summarize } from "./Meter";

export function SystemCard({ history }: { history: SystemSnapshot[] }) {
  const system = history[history.length - 1];
  const memory = history.map((snapshot) => snapshot.memory_used_mb);
  const utilization = history.map((snapshot) => snapshot.cpu_utilization_pct);
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4 shadow-lg shadow-black/10">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex min-w-0 gap-1 text-sm font-semibold text-zinc-100">
          <span className="text-zinc-500">CPU</span>
          <span className="truncate" title={system.cpu_name}>
            {system.cpu_name || "Host"}
          </span>
        </div>
        <div className="shrink-0 font-mono text-xs text-zinc-400">
          {system.cpu_threads} threads
          {system.swap_total_mb > 0
            ? ` · swap ${formatGiB(system.swap_used_mb)} / ${formatGiB(system.swap_total_mb)} GiB`
            : null}
        </div>
      </div>
      <div className="mt-3 space-y-3">
        <Meter
          fraction={system.memory_total_mb > 0 ? system.memory_used_mb / system.memory_total_mb : null}
          history={memory}
          historyLabel={`RAM history, ${summarize(memory, "GiB")}`}
          label="RAM"
          max={system.memory_total_mb}
          value={`${formatGiB(system.memory_used_mb)} / ${formatGiB(system.memory_total_mb)} GiB`}
        />
        <Meter
          fraction={system.cpu_utilization_pct != null ? system.cpu_utilization_pct / 100 : null}
          history={utilization}
          historyLabel={`CPU utilisation history, ${summarize(utilization, "%")}`}
          label="CPU"
          max={100}
          value={
            system.cpu_utilization_pct != null ? `${system.cpu_utilization_pct.toFixed(0)}%` : "n/a"
          }
        />
      </div>
      {system.processes.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {system.processes.map((process) => (
            <span
              className="rounded-md border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-xs text-zinc-300"
              key={process.pid}
            >
              {process.profile_name}
              <span className="ml-1.5 font-mono text-zinc-500">{formatGiB(process.rss_mb)} GiB</span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
