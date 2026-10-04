import { useEffect, useState } from "react";

import { gpuStreamUrl, type GpuSnapshot } from "../../api";

const MAX_SAMPLES = 300;

export type GpuStream = {
  history: GpuSnapshot[];
  error: string | null;
  connected: boolean;
};

export function useGpuStream(): GpuStream {
  const [history, setHistory] = useState<GpuSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(gpuStreamUrl());
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("history", (event) => {
      const { snapshots } = JSON.parse((event as MessageEvent).data) as {
        snapshots: GpuSnapshot[];
      };
      setHistory(snapshots.slice(-MAX_SAMPLES));
    });
    source.addEventListener("snapshot", (event) => {
      const snapshot = JSON.parse((event as MessageEvent).data) as GpuSnapshot;
      setHistory((current) => [...current, snapshot].slice(-MAX_SAMPLES));
    });
    source.addEventListener("status", (event) => {
      setError((JSON.parse((event as MessageEvent).data) as { error: string | null }).error);
    });
    return () => source.close();
  }, []);

  return { history, error, connected };
}
