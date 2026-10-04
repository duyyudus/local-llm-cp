import { GpuCard } from "./GpuCard";
import { SystemCard } from "./SystemCard";
import type { MetricsStream } from "./useMetricsStream";

function Placeholder({ children }: { children: string }) {
  return (
    <div className="flex items-center justify-center rounded-xl border border-zinc-800/80 bg-zinc-900/60 px-4 py-6 text-center text-sm text-zinc-500">
      {children}
    </div>
  );
}

export function MetricsPanel({ stream }: { stream: MetricsStream }) {
  const { gpu, system, connected } = stream;
  const latest = gpu.history[gpu.history.length - 1];
  const waiting = (what: string) => (connected ? `Waiting for ${what} data` : "Connecting to the API");
  return (
    <div>
      {latest && gpu.error ? (
        <div className="mb-2 text-xs text-warning">GPU data is stale: {gpu.error}</div>
      ) : null}
      {system.history.length > 0 && system.error ? (
        <div className="mb-2 text-xs text-warning">CPU and memory data is stale: {system.error}</div>
      ) : null}
      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(18rem,1fr))]">
        {latest ? (
          latest.gpus.map((item) => <GpuCard gpu={item} history={gpu.history} key={item.index} />)
        ) : (
          <Placeholder>{gpu.error ?? waiting("GPU")}</Placeholder>
        )}
        {system.history.length > 0 ? (
          <SystemCard history={system.history} />
        ) : (
          <Placeholder>{system.error ?? waiting("CPU and memory")}</Placeholder>
        )}
      </div>
    </div>
  );
}
