import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api";
import { classNames } from "../../lib/classNames";

const CONFIG_FILE = /^config.*\.ya?ml$/i;

type Listing = { files: string[] } | { error: string };

/** One-click choice of the config*.yml files at the top of a repository folder. */
export function RepoConfigs({
  repo,
  value,
  onChange,
}: {
  repo: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [listing, setListing] = useState<Listing | null>(null);
  const [reload, setReload] = useState(0);
  const folder = repo.trim();

  useEffect(() => {
    setListing(null);
    if (!folder) return;
    let cancelled = false;
    // Wait for the folder to be typed out before asking the host.
    const timer = window.setTimeout(() => {
      api
        .browse(folder)
        .then((result) => {
          if (cancelled) return;
          const files = result.entries
            .filter((entry) => !entry.is_dir && CONFIG_FILE.test(entry.name))
            .map((entry) => entry.name)
            .sort();
          setListing({ files });
        })
        .catch(() => {
          if (!cancelled) setListing({ error: "Cannot read this folder on the GPU host." });
        });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [folder, reload]);

  if (!folder) return null;

  let body;
  if (listing === null) {
    body = <span className="text-xs text-zinc-500">Looking for config files…</span>;
  } else if ("error" in listing) {
    body = <span className="text-xs text-zinc-500">{listing.error}</span>;
  } else if (listing.files.length === 0) {
    body = <span className="text-xs text-zinc-500">No config*.yml in the repository.</span>;
  } else {
    body = listing.files.map((name) => {
      const selected = value.trim() === name;
      return (
        <button
          aria-pressed={selected}
          className={classNames(
            "btn btn-xs font-mono font-normal normal-case",
            selected ? "btn-primary" : "btn-outline border-zinc-700 text-zinc-300",
          )}
          key={name}
          // Picking the selected file again goes back to tabbyAPI's own config.yml.
          onClick={() => onChange(selected ? "" : name)}
          type="button"
        >
          {name}
        </button>
      );
    });
  }

  return (
    <div className="-mt-1 sm:col-span-2">
      <div className="mb-1 flex items-center gap-1">
        <span className="text-xs text-zinc-400">Configs in the repository</span>
        <button
          aria-label="Refresh config files"
          className="btn btn-ghost btn-xs px-1"
          onClick={() => setReload(reload + 1)}
          type="button"
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">{body}</div>
    </div>
  );
}
