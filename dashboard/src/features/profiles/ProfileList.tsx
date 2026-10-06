import {
  Copy,
  Download,
  GripVertical,
  Pencil,
  Play,
  Plus,
  Square,
  Trash2,
  Upload,
} from "lucide-react";
import { useRef, useState } from "react";

import type { Profile } from "../../api";
import { classNames } from "../../lib/classNames";
import { baseName, formatUptime } from "../../lib/format";
import { RunStatusBadge, isActive } from "./status";

type DropTarget = { id: string; after: boolean };

function moveTo(ids: string[], id: string, target: DropTarget): string[] {
  if (id === target.id) return ids;
  const rest = ids.filter((other) => other !== id);
  rest.splice(rest.indexOf(target.id) + (target.after ? 1 : 0), 0, id);
  return rest;
}

export function ProfileList({
  profiles,
  loading,
  selectedId,
  busyId,
  now,
  onSelect,
  onCreate,
  onEdit,
  onDuplicate,
  onDelete,
  onExport,
  onImport,
  onReorder,
  onStart,
  onStop,
}: {
  profiles: Profile[];
  loading: boolean;
  selectedId: string | null;
  busyId: string | null;
  now: number;
  onSelect: (profile: Profile) => void;
  onCreate: () => void;
  onEdit: (profile: Profile) => void;
  onDuplicate: (profile: Profile) => void;
  onDelete: (profile: Profile) => void;
  onExport: (profile: Profile | null) => void;
  onImport: (file: File) => void;
  onReorder: (ids: string[]) => void;
  onStart: (profile: Profile) => void;
  onStop: (profile: Profile) => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const ids = profiles.map((profile) => profile.id);

  function reorder(next: string[]) {
    if (next.join() !== ids.join()) onReorder(next);
  }

  function endDrag() {
    setDragId(null);
    setDropTarget(null);
  }

  function dragOver(event: React.DragEvent<HTMLLIElement>, id: string) {
    // Only rows of this list can be dropped here, not files or text from elsewhere.
    if (!dragId) return;
    event.preventDefault();
    const box = event.currentTarget.getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    if (dropTarget?.id !== id || dropTarget.after !== after) setDropTarget({ id, after });
  }

  function drop(event: React.DragEvent<HTMLLIElement>) {
    if (!dragId) return;
    event.preventDefault();
    if (dropTarget) reorder(moveTo(ids, dragId, dropTarget));
    endDrag();
  }

  function moveWithKeys(event: React.KeyboardEvent<HTMLDivElement>, id: string) {
    const step = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
    const index = ids.indexOf(id) + step;
    if (step === 0 || index < 0 || index >= ids.length) return;
    event.preventDefault();
    reorder(moveTo(ids, id, { id: ids[index], after: step > 0 }));
    // Moving the row in the DOM can drop focus, which would end the keyboard move.
    const handle = event.currentTarget;
    requestAnimationFrame(() => handle.focus());
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800/60 px-4 py-3">
        <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-200">
          Profiles <span className="font-normal text-zinc-500">{profiles.length}</span>
        </h2>
        <div className="flex items-center gap-1">
          <input
            accept=".json,application/json"
            className="hidden"
            data-testid="import-file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Reset so choosing the same file again still fires a change.
              event.target.value = "";
              if (file) onImport(file);
            }}
            ref={fileInput}
            type="file"
          />
          <button
            aria-label="Import profiles"
            className="btn btn-sm btn-ghost"
            onClick={() => fileInput.current?.click()}
            title="Import profiles from a JSON file"
            type="button"
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            aria-label="Export all profiles"
            className="btn btn-sm btn-ghost"
            disabled={profiles.length === 0}
            onClick={() => onExport(null)}
            title="Export all profiles to a JSON file"
            type="button"
          >
            <Upload className="h-4 w-4" />
          </button>
          <button className="btn btn-sm btn-primary" onClick={onCreate} type="button">
            <Plus className="h-4 w-4" />
            New profile
          </button>
        </div>
      </div>
      <ul
        className="min-h-0 flex-1 overflow-y-auto"
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setDropTarget(null);
          }
        }}
      >
        {profiles.length === 0 ? (
          <li className="px-4 py-10 text-center text-sm text-zinc-500">
            {loading
              ? "Loading profiles"
              : "No profiles yet. Create one to replace a launch script."}
          </li>
        ) : null}
        {profiles.map((profile) => {
          const active = isActive(profile.run.status);
          const busy = busyId === profile.id;
          const target = dropTarget?.id === profile.id && dragId !== profile.id ? dropTarget : null;
          return (
            <li
              className={classNames(
                "group relative border-b border-zinc-800/60 border-l-[3px] py-3 pl-1 pr-4 transition-colors",
                selectedId === profile.id
                  ? "border-l-primary bg-primary/10"
                  : "border-l-transparent hover:bg-zinc-800/30",
                dragId === profile.id && "opacity-40",
              )}
              key={profile.id}
              onDragOver={(event) => dragOver(event, profile.id)}
              onDrop={drop}
            >
              {target ? (
                <div
                  className={classNames(
                    "pointer-events-none absolute inset-x-0 h-0.5 bg-primary",
                    target.after ? "bottom-0" : "top-0",
                  )}
                  data-testid="drop-indicator"
                />
              ) : null}
              <div className="flex items-start gap-1">
                {/* Not a <button>: Firefox does not start a drag from one. */}
                <div
                  aria-label={`Reorder ${profile.name}`}
                  className="shrink-0 cursor-grab rounded px-0.5 py-1 text-zinc-600 hover:text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary active:cursor-grabbing"
                  draggable
                  onDragEnd={endDrag}
                  onDragStart={(event) => {
                    const row = event.currentTarget.closest("li");
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", profile.name);
                    if (row) event.dataTransfer.setDragImage(row, 12, 12);
                    setDragId(profile.id);
                  }}
                  onKeyDown={(event) => moveWithKeys(event, profile.id)}
                  role="button"
                  tabIndex={0}
                  title="Drag to reorder, or use the arrow keys"
                >
                  <GripVertical className="h-4 w-4" />
                </div>
                <button
                  className="mr-2 min-w-0 flex-1 text-left"
                  onClick={() => onSelect(profile)}
                  title={profile.command}
                  type="button"
                >
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-zinc-100">
                      {profile.name}
                    </span>
                    <RunStatusBadge status={profile.run.status} />
                  </div>
                  <div className="mt-1 truncate font-mono text-xs text-zinc-400">
                    {profile.engine === "comfyui"
                      ? baseName(profile.working_dir)
                      : baseName(profile.model_path) || baseName(profile.executable_path)}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-zinc-500">
                    <span className="font-mono">
                      {profile.host}:{profile.port}
                    </span>
                    {profile.alias ? <span>alias {profile.alias}</span> : null}
                    {profile.ctx_size != null ? <span>ctx {profile.ctx_size}</span> : null}
                    {profile.env.CUDA_VISIBLE_DEVICES ? (
                      <span>gpu {profile.env.CUDA_VISIBLE_DEVICES}</span>
                    ) : null}
                    {active && profile.run.pid ? (
                      <span>
                        pid {profile.run.pid}, up {formatUptime(profile.run.started_at, now)}
                      </span>
                    ) : null}
                  </div>
                  {active && profile.run.command_changed ? (
                    <div className="mt-1 text-xs text-warning">
                      Edited since launch. Restart to apply.
                    </div>
                  ) : null}
                </button>
                {active ? (
                  <button
                    className="btn btn-sm btn-outline btn-error shrink-0"
                    disabled={busy}
                    onClick={() => onStop(profile)}
                    type="button"
                  >
                    <Square className="h-3.5 w-3.5" />
                    Stop
                  </button>
                ) : (
                  <button
                    className="btn btn-sm btn-outline btn-primary shrink-0"
                    disabled={busy}
                    onClick={() => onStart(profile)}
                    type="button"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Start
                  </button>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1 pl-6">
                <button className="btn btn-xs btn-ghost" onClick={() => onEdit(profile)} type="button">
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </button>
                <button
                  className="btn btn-xs btn-ghost"
                  onClick={() => onDuplicate(profile)}
                  type="button"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Duplicate
                </button>
                <button
                  className="btn btn-xs btn-ghost"
                  onClick={() => onExport(profile)}
                  type="button"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Export
                </button>
                <button
                  className="btn btn-xs btn-ghost text-error"
                  disabled={active}
                  onClick={() => onDelete(profile)}
                  title={active ? "Stop the profile before deleting it" : undefined}
                  type="button"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
