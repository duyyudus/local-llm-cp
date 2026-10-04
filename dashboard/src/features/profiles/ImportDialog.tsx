import { Download } from "lucide-react";

import type { ImportConflict } from "../../api";

export function ImportDialog({
  total,
  conflicts,
  onImport,
  onCancel,
}: {
  total: number;
  conflicts: string[];
  onImport: (onConflict: ImportConflict) => void;
  onCancel: () => void;
}) {
  return (
    <div className="modal modal-open" role="dialog" aria-label="Import profiles">
      <div className="modal-box border border-zinc-700 bg-zinc-900">
        <div className="flex items-start gap-3">
          <Download className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="min-w-0">
            <h3 className="text-base font-bold text-zinc-100">Import profiles</h3>
            <p className="mt-1 text-sm text-zinc-400">
              {conflicts.length} of {total} profiles in this file already exist:
            </p>
            <ul className="mt-2 max-h-40 overflow-y-auto font-mono text-xs text-zinc-300">
              {conflicts.map((name) => (
                <li className="truncate" key={name}>
                  {name}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="modal-action flex-wrap">
          <button className="btn btn-sm btn-ghost" onClick={onCancel} type="button">
            Cancel
          </button>
          <button className="btn btn-sm" onClick={() => onImport("skip")} type="button">
            Skip existing
          </button>
          <button className="btn btn-sm" onClick={() => onImport("rename")} type="button">
            Keep both
          </button>
          <button className="btn btn-sm btn-warning" onClick={() => onImport("overwrite")} type="button">
            Overwrite
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onCancel} />
    </div>
  );
}
