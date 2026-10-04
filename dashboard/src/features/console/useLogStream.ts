import { useEffect, useRef, useState } from "react";

import { logStreamUrl } from "../../api";

const MAX_LINES = 5000;

export type LogStream = {
  lines: string[];
  connected: boolean;
  clear: () => void;
};

export function useLogStream(profileId: string | null): LogStream {
  const buffer = useRef<string[]>([]);
  const frame = useRef<number | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);

  // Bursts of log events are coalesced into one render per animation frame.
  const flush = () => {
    if (frame.current != null) return;
    frame.current = window.requestAnimationFrame(() => {
      frame.current = null;
      setLines(buffer.current);
    });
  };

  const clear = () => {
    buffer.current = [];
    flush();
  };

  useEffect(() => {
    buffer.current = [];
    setLines([]);
    setConnected(false);
    if (!profileId) return;
    const source = new EventSource(logStreamUrl(profileId));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    // The server sends "reset" on every (re)connect and on a new launch, then the backlog.
    source.addEventListener("reset", () => {
      buffer.current = [];
      flush();
    });
    source.addEventListener("lines", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { lines: string[] };
      buffer.current = [...buffer.current, ...payload.lines].slice(-MAX_LINES);
      flush();
    });
    return () => {
      source.close();
      if (frame.current != null) {
        window.cancelAnimationFrame(frame.current);
        frame.current = null;
      }
    };
  }, [profileId]);

  return { lines, connected, clear };
}
