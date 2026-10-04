import type { Gpu, GpuSnapshot } from "../../api";
import { formatGiB } from "../../lib/format";
import { Meter, summarize } from "./Meter";

export function GpuCard({ gpu, history }: { gpu: Gpu; history: GpuSnapshot[] }) {
  const series = history.map((snapshot) => snapshot.gpus.find((item) => item.index === gpu.index));
  const memory = series.map((item) => item?.memory_used_mb ?? null);
  const utilization = series.map((item) => item?.utilization_pct ?? null);
  const total = gpu.memory_total_mb ?? 0;
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4 shadow-lg shadow-black/10">
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0 truncate text-sm font-semibold text-zinc-100">
          <span className="text-zinc-500">GPU {gpu.index}</span> {gpu.name.replace(/^NVIDIA /, "")}
        </div>
        <div className="shrink-0 font-mono text-xs text-zinc-400">
          {gpu.temperature_c != null ? `${gpu.temperature_c.toFixed(0)}°C` : null}
          {gpu.temperature_c != null && gpu.power_w != null ? " · " : null}
          {gpu.power_w != null ? `${gpu.power_w.toFixed(0)} W` : null}
        </div>
      </div>
      <div className="mt-3 space-y-3">
        <Meter
          fraction={gpu.memory_used_mb != null && total > 0 ? gpu.memory_used_mb / total : null}
          history={memory}
          historyLabel={`GPU ${gpu.index} VRAM history, ${summarize(memory, "GiB")}`}
          label="VRAM"
          max={total}
          value={`${formatGiB(gpu.memory_used_mb)} / ${formatGiB(gpu.memory_total_mb)} GiB`}
        />
        <Meter
          fraction={gpu.utilization_pct != null ? gpu.utilization_pct / 100 : null}
          history={utilization}
          historyLabel={`GPU ${gpu.index} utilisation history, ${summarize(utilization, "%")}`}
          label="Compute"
          max={100}
          value={gpu.utilization_pct != null ? `${gpu.utilization_pct.toFixed(0)}%` : "n/a"}
        />
      </div>
      {gpu.processes.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {gpu.processes.map((process) => (
            <span
              className="rounded-md border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-xs text-zinc-300"
              key={process.pid}
            >
              {process.profile_name ?? `pid ${process.pid}`}
              {process.used_mb != null ? (
                <span className="ml-1.5 font-mono text-zinc-500">
                  {formatGiB(process.used_mb)} GiB
                </span>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
