import { ArrowDownToLine, Eraser, TerminalSquare, WrapText } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { Profile } from "../../api";
import { classNames } from "../../lib/classNames";
import { RunStatusBadge } from "../profiles/status";
import { useLogStream } from "./useLogStream";

const STICK_THRESHOLD_PX = 24;

export function ConsolePanel({
  tabs,
  selected,
  onSelect,
}: {
  tabs: Profile[];
  selected: Profile | null;
  onSelect: (profile: Profile) => void;
}) {
  const { lines, connected, clear } = useLogStream(selected?.id ?? null);
  const [wrap, setWrap] = useState(() => localStorage.getItem("llm-cp-console-wrap") !== "off");
  const [following, setFollowing] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);
  const text = useMemo(() => lines.join("\n"), [lines]);

  useEffect(() => {
    localStorage.setItem("llm-cp-console-wrap", wrap ? "on" : "off");
  }, [wrap]);

  useEffect(() => setFollowing(true), [selected?.id]);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && following) element.scrollTop = element.scrollHeight;
  }, [text, following, wrap]);

  function onScroll() {
    const element = scroller.current;
    if (!element) return;
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    setFollowing(distance <= STICK_THRESHOLD_PX);
  }

  return (
    <section
      aria-label="Console"
      className="flex min-h-[20rem] flex-1 flex-col overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/60 shadow-lg shadow-black/10"
    >
      <div className="flex items-center gap-2 border-b border-zinc-800/60 bg-zinc-900/40 pr-2">
        <div className="flex min-w-0 flex-1 overflow-x-auto" role="tablist">
          {tabs.length === 0 ? (
            <div className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold uppercase tracking-widest text-zinc-200">
              <TerminalSquare className="h-4 w-4" />
              Console
            </div>
          ) : null}
          {tabs.map((profile) => (
            <button
              aria-selected={profile.id === selected?.id}
              className={classNames(
                "flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 text-sm transition-colors",
                profile.id === selected?.id
                  ? "border-primary font-semibold text-zinc-100"
                  : "border-transparent text-zinc-400 hover:text-zinc-100",
              )}
              key={profile.id}
              onClick={() => onSelect(profile)}
              role="tab"
              type="button"
            >
              {profile.name}
              <RunStatusBadge status={profile.run.status} />
            </button>
          ))}
        </div>
        {selected ? (
          <div className="flex shrink-0 items-center gap-1">
            {!connected ? <span className="mr-1 text-xs text-warning">reconnecting</span> : null}
            <span className="mr-1 font-mono text-xs text-zinc-500">{lines.length} lines</span>
            <button
              aria-pressed={wrap}
              className={classNames("btn btn-xs", wrap ? "btn-outline btn-primary" : "btn-ghost")}
              onClick={() => setWrap(!wrap)}
              title="Wrap long lines"
              type="button"
            >
              <WrapText className="h-3.5 w-3.5" />
              Wrap
            </button>
            <button className="btn btn-xs btn-ghost" onClick={clear} title="Clear view" type="button">
              <Eraser className="h-3.5 w-3.5" />
              Clear
            </button>
          </div>
        ) : null}
      </div>
      <div className="relative min-h-0 flex-1">
        <div
          className="absolute inset-0 overflow-auto bg-zinc-950 px-4 py-3"
          onScroll={onScroll}
          ref={scroller}
        >
          {selected ? (
            <pre
              className={classNames(
                "console-output text-zinc-300",
                wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre",
              )}
              data-testid="console-output"
            >
              {text || <span className="text-zinc-600">No log output yet.</span>}
            </pre>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-zinc-500">
              Select or start a profile to see its server log.
            </div>
          )}
        </div>
        {selected && !following ? (
          <button
            className="btn btn-sm btn-primary absolute bottom-3 right-5 shadow-lg"
            onClick={() => setFollowing(true)}
            type="button"
          >
            <ArrowDownToLine className="h-4 w-4" />
            Jump to latest
          </button>
        ) : null}
      </div>
    </section>
  );
}
