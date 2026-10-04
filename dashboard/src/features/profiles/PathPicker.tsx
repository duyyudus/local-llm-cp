import { CornerLeftUp, File, Folder, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, type DirListing } from "../../api";
import { errorMessage, formatBytes } from "../../lib/format";

function startDirectory(value: string): string {
  const index = value.lastIndexOf("/");
  return index > 0 ? value.slice(0, index) : "~";
}

export function PathPicker({
  title,
  initialValue,
  onSelect,
  onCancel,
}: {
  title: string;
  initialValue: string;
  onSelect: (path: string) => void;
  onCancel: () => void;
}) {
  const [listing, setListing] = useState<DirListing | null>(null);
  const [pathInput, setPathInput] = useState(startDirectory(initialValue));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const result = await api.browse(path);
      setListing(result);
      setPathInput(result.path);
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(startDirectory(initialValue));
  }, [initialValue, load]);

  const join = (name: string) => `${listing?.path === "/" ? "" : listing?.path}/${name}`;

  return (
    <div className="modal modal-open z-50" role="dialog" aria-label={title}>
      <div className="modal-box flex max-h-[80vh] max-w-2xl flex-col border border-zinc-700 bg-zinc-900 p-0">
        <div className="border-b border-zinc-800 px-5 py-3">
          <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-200">{title}</h3>
          <form
            className="mt-2 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void load(pathInput);
            }}
          >
            <button
              aria-label="Parent folder"
              className="btn btn-sm btn-ghost"
              disabled={!listing?.parent}
              onClick={() => listing?.parent && void load(listing.parent)}
              type="button"
            >
              <CornerLeftUp className="h-4 w-4" />
            </button>
            <input
              aria-label="Folder path"
              className="input input-bordered input-sm min-w-0 flex-1 font-mono text-xs"
              onChange={(event) => setPathInput(event.target.value)}
              value={pathInput}
            />
            <button className="btn btn-sm btn-outline" type="submit">
              <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Go
            </button>
          </form>
        </div>
        {error ? <div className="alert alert-error m-3 text-sm">{error}</div> : null}
        <ul className="min-h-40 flex-1 overflow-y-auto py-1">
          {listing?.entries.map((entry) => (
            <li key={entry.name}>
              <button
                className="flex w-full items-center gap-2 px-5 py-1.5 text-left text-sm text-zinc-300 hover:bg-zinc-800/60"
                onClick={() =>
                  entry.is_dir ? void load(join(entry.name)) : onSelect(join(entry.name))
                }
                type="button"
              >
                {entry.is_dir ? (
                  <Folder className="h-4 w-4 shrink-0 text-primary" />
                ) : (
                  <File className="h-4 w-4 shrink-0 text-zinc-500" />
                )}
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{entry.name}</span>
                <span className="shrink-0 text-xs text-zinc-500">{formatBytes(entry.size)}</span>
              </button>
            </li>
          ))}
          {listing && listing.entries.length === 0 ? (
            <li className="px-5 py-6 text-center text-sm text-zinc-500">Empty folder</li>
          ) : null}
        </ul>
        <div className="flex justify-end border-t border-zinc-800 px-5 py-3">
          <button className="btn btn-sm btn-ghost" onClick={onCancel} type="button">
            Cancel
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onCancel} />
    </div>
  );
}
