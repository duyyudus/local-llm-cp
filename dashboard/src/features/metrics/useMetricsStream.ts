import { useEffect, useState } from "react";

import { hostStreamUrl, type GpuSnapshot, type SystemSnapshot } from "../../api";

const MAX_SAMPLES = 300;

export type Feed<T> = { history: T[]; error: string | null };

export type MetricsStream = {
  gpu: Feed<GpuSnapshot>;
  system: Feed<SystemSnapshot>;
  connected: boolean;
};

const EMPTY = { history: [], error: null };

export function useMetricsStream(): MetricsStream {
  const [gpu, setGpu] = useState<Feed<GpuSnapshot>>(EMPTY);
  const [system, setSystem] = useState<Feed<SystemSnapshot>>(EMPTY);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(hostStreamUrl());
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    function follow<T>(name: string, update: (change: (feed: Feed<T>) => Feed<T>) => void) {
      source.addEventListener(`${name}_history`, (event) => {
        const { snapshots } = JSON.parse((event as MessageEvent).data) as { snapshots: T[] };
        update((feed) => ({ ...feed, history: snapshots.slice(-MAX_SAMPLES) }));
      });
      source.addEventListener(`${name}_snapshot`, (event) => {
        const snapshot = JSON.parse((event as MessageEvent).data) as T;
        update((feed) => ({ ...feed, history: [...feed.history, snapshot].slice(-MAX_SAMPLES) }));
      });
      source.addEventListener(`${name}_status`, (event) => {
        const { error } = JSON.parse((event as MessageEvent).data) as { error: string | null };
        update((feed) => ({ ...feed, error }));
      });
    }

    follow<GpuSnapshot>("gpu", setGpu);
    follow<SystemSnapshot>("system", setSystem);
    return () => source.close();
  }, []);

  return { gpu, system, connected };
}
